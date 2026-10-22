"""Sınırlı SQLite yedekleri ve taşınabilir JSON aktarımı."""
from __future__ import annotations

import json
import math
import re
import sqlite3
import tempfile
from contextlib import closing
from datetime import date, datetime
from pathlib import Path

from .model import Store
from .schedule import next_occurrence


class Backups:
    def __init__(self, store: Store):
        self.store = store
        self.directory = store.path.parent / "backups"

    def snapshot(self, daily: bool = False) -> Path | None:
        self.directory.mkdir(exist_ok=True)
        if daily and any(self.directory.glob(f"odak-{date.today().isoformat()}-*.sqlite3")):
            return None
        target = self.directory / f"odak-{datetime.now():%Y-%m-%d-%H%M%S-%f}.sqlite3"
        try:
            with closing(sqlite3.connect(target)) as destination:
                self.store.db.backup(destination)
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        own = sorted(p for p in self.directory.glob("odak-*.sqlite3")
                     if re.fullmatch(r"odak-\d{4}-\d{2}-\d{2}-\d{6}-\d{6}\.sqlite3", p.name))
        for old in own[:-3]:
            old.unlink()
        return target

    def restore(self, source: Path):
        if source.resolve() == self.store.path:
            raise ValueError("Etkin veritabanı zaten açık.")
        with tempfile.TemporaryDirectory(dir=self.store.path.parent) as directory:
            staged = Path(directory) / "restore.sqlite3"
            with closing(sqlite3.connect(staged)) as temporary:
                with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as incoming:
                    if incoming.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                        raise ValueError("Yedek dosyası okunamadı.")
                    columns = {r[1] for r in incoming.execute("PRAGMA table_info(tasks)")}
                    if not {"id", "title", "notes", "deadline", "has_time", "completed_at", "deleted_at", "created_at"} <= columns:
                        raise ValueError("Bu bir Odak yedeği değil.")
                    incoming.backup(temporary)
                # Windows'ta eski yedek silinmeden önce kaynak bağlantısını kapat.
                self.snapshot()
                temporary.backup(self.store.db)
        self.store.ensure_schema()


def export_json(store: Store, target: Path):
    data = {"format": "odak", "version": 1,
            "exported_at": datetime.now().isoformat(),
            "tasks": [dict(r) for r in store.db.execute("SELECT * FROM tasks")],
            "steps": [dict(r) for r in store.db.execute("SELECT * FROM steps ORDER BY position")],
            "reminders": [dict(r) for r in store.db.execute("SELECT * FROM reminders")]}
    contents = json.dumps(data, ensure_ascii=False, indent=2)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent,
                                     prefix=".odak-", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(contents)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def import_json(store: Store, source: Path) -> int:
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("format") != "odak" or data.get("version") != 1:
        raise ValueError("Geçerli bir Odak JSON dosyası seç.")
    tasks, steps, reminders = (data.get(k, []) for k in ("tasks", "steps", "reminders"))
    if not all(isinstance(items, list) for items in (tasks, steps, reminders)):
        raise ValueError("Dosya yapısı geçersiz.")

    def identity(value):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{32}", value):
            raise ValueError("Dosyada geçersiz kayıt kimliği var.")

    def text(value, title=False):
        if not isinstance(value, str) or (title and (not value.strip() or len(value) > 180)):
            raise ValueError("Dosyada geçersiz metin var.")

    def stamp(value, optional=True):
        if value is None and optional:
            return
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("Dosyada geçersiz zaman var.")

    def local_date(value):
        if value is not None and (not isinstance(value, str) or datetime.fromisoformat(value).tzinfo is not None):
            raise ValueError("Dosyada geçersiz tarih var.")

    seen = set()
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("Geçersiz görev kaydı.")
        identity(task.get("id")); text(task.get("title"), True); text(task.get("notes", ""))
        if task["id"] in seen:
            raise ValueError("Dosyada yinelenen görev kimliği var.")
        seen.add(task["id"])
        local_date(task.get("deadline"))
        if task.get("today") is not None:
            date.fromisoformat(task["today"])
        for key in ("completed_at", "deleted_at"):
            stamp(task.get(key))
        stamp(task.get("created_at"), False)
    for step in steps:
        identity(step.get("id")); identity(step.get("task_id")); text(step.get("title"), True)
        if step["task_id"] not in seen or type(step.get("position")) is not int:
            raise ValueError("Alt adımın görevi veya sırası geçersiz.")
    reminder_ids = set()
    for reminder in reminders:
        identity(reminder.get("id")); text(reminder.get("title"), True); text(reminder.get("notes", ""))
        if reminder["id"] in reminder_ids:
            raise ValueError("Dosyada yinelenen hatırlatma kimliği var.")
        reminder_ids.add(reminder["id"])
        days = json.loads(reminder["weekdays"])
        if not isinstance(days, list):
            raise ValueError("Tekrar günleri geçersiz.")
        next_occurrence(days, reminder["clock"])
        local_date(reminder["next_at"]); local_date(reminder.get("snooze_at"))
        stamp(reminder.get("deleted_at")); stamp(reminder.get("created_at"), False)
    added = set()
    count = 0
    with store.db:
        for task in tasks:
            if store.db.execute("SELECT 1 FROM tasks WHERE id=?", (task["id"],)).fetchone():
                continue
            store.db.execute("INSERT INTO tasks (id,title,notes,deadline,has_time,completed_at,deleted_at,created_at,today,someday) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (task["id"], task["title"], task.get("notes", ""), task.get("deadline"), int(bool(task.get("has_time"))),
                 task.get("completed_at"), task.get("deleted_at"), task["created_at"], task.get("today"), int(bool(task.get("someday")))))
            added.add(task["id"])
            count += 1
        for step in steps:
            if step["task_id"] in added:
                store.db.execute("INSERT INTO steps VALUES (?,?,?,?,?)",
                    (step["id"], step["task_id"], step["title"], int(bool(step.get("done"))), step["position"]))
        for r in reminders:
            cursor = store.db.execute("INSERT OR IGNORE INTO reminders (id,title,notes,weekdays,clock,paused,next_at,snooze_at,deleted_at,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (r["id"], r["title"], r.get("notes", ""), r["weekdays"], r["clock"], int(bool(r.get("paused"))),
                 r["next_at"], r.get("snooze_at"), r.get("deleted_at"), r["created_at"]))
            count += cursor.rowcount
    return count
