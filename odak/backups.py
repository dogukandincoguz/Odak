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

from .model import Store, ORDERED_LISTS
from .recurrence import validate_rule, meeting_link, LEADS


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
            "task_order": [dict(r) for r in store.db.execute("SELECT * FROM task_order ORDER BY scope,position")],
            "reminders": [dict(r) for r in store.db.execute("SELECT * FROM reminders")],
            "templates": [dict(r) for r in store.db.execute("SELECT * FROM templates")]}
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
    tasks, steps, reminders, templates = (data.get(k, []) for k in ("tasks", "steps", "reminders", "templates"))
    if not all(isinstance(items, list) for items in (tasks, steps, reminders, templates)):
        raise ValueError("Dosya yapısı geçersiz.")
    task_order = data.get("task_order", [])
    if not isinstance(task_order, list):
        raise ValueError("Görev sırası geçersiz.")

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
        if task.get("today_position") is not None and (type(task["today_position"]) is not int or task["today_position"] < 0):
            raise ValueError("Görev sırası geçersiz.")
        for key in ("completed_at", "deleted_at"):
            stamp(task.get(key))
        stamp(task.get("created_at"), False)
    for step in steps:
        identity(step.get("id")); identity(step.get("task_id")); text(step.get("title"), True)
        if step["task_id"] not in seen or type(step.get("position")) is not int:
            raise ValueError("Alt adımın görevi veya sırası geçersiz.")
    order_ids, order_positions = set(), set()
    for item in task_order:
        if not isinstance(item, dict) or item.get("scope") not in ORDERED_LISTS:
            raise ValueError("Görev sırası geçersiz.")
        identity(item.get("task_id"))
        scope, task_id, position = item["scope"], item["task_id"], item.get("position")
        if (task_id not in seen or type(position) is not int or position < 0
                or (scope, task_id) in order_ids or (scope, position) in order_positions):
            raise ValueError("Görev sırası geçersiz.")
        order_ids.add((scope, task_id)); order_positions.add((scope, position))
    reminder_ids = set()
    for reminder in reminders:
        identity(reminder.get("id")); text(reminder.get("title"), True); text(reminder.get("notes", ""))
        if reminder["id"] in reminder_ids:
            raise ValueError("Dosyada yinelenen hatırlatma kimliği var.")
        reminder_ids.add(reminder["id"])
        days = json.loads(reminder["weekdays"])
        if not isinstance(days, list):
            raise ValueError("Tekrar günleri geçersiz.")
        for key, default in dict(kind="weekly", interval=1, anchor_date="1970-01-01", month_day=1,
                                 ordinal=-1, month_weekday=4, lead_minutes=0, link="", notified_for=None, expires_at=None).items():
            reminder.setdefault(key, default)
        validate_rule(reminder["kind"], days, reminder["clock"], date.fromisoformat(reminder["anchor_date"]),
                      reminder["interval"], reminder["month_day"], reminder["ordinal"], reminder["month_weekday"])
        if type(reminder["lead_minutes"]) is not int or reminder["lead_minutes"] not in LEADS:
            raise ValueError("Bildirim zamanı geçersiz.")
        text(reminder["link"])
        reminder["link"] = meeting_link(reminder["link"])
        local_date(reminder["notified_for"]); local_date(reminder["expires_at"])
        local_date(reminder["next_at"]); local_date(reminder.get("snooze_at"))
        stamp(reminder.get("deleted_at")); stamp(reminder.get("created_at"), False)
    template_ids = set()
    for template in templates:
        identity(template.get("id")); text(template.get("title"), True); text(template.get("name"), True)
        if len(template["name"]) > 80 or template["id"] in template_ids:
            raise ValueError("Şablon adı veya kimliği geçersiz.")
        template_ids.add(template["id"])
        text(template.get("notes", "")); stamp(template.get("created_at"), False)
        items = json.loads(template["steps"])
        if not isinstance(items, list):
            raise ValueError("Şablon adımları geçersiz.")
        for item in items:
            text(item, True)
    added = set()
    count = 0
    with store.db:
        for task in tasks:
            if store.db.execute("SELECT 1 FROM tasks WHERE id=?", (task["id"],)).fetchone():
                continue
            store.db.execute("INSERT INTO tasks (id,title,notes,deadline,has_time,completed_at,deleted_at,created_at,today,someday,today_position) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (task["id"], task["title"], task.get("notes", ""), task.get("deadline"), int(bool(task.get("has_time"))),
                 task.get("completed_at"), task.get("deleted_at"), task["created_at"], task.get("today"), int(bool(task.get("someday"))), task.get("today_position")))
            added.add(task["id"])
            count += 1
        for step in steps:
            if step["task_id"] in added:
                store.db.execute("INSERT INTO steps VALUES (?,?,?,?,?)",
                    (step["id"], step["task_id"], step["title"], int(bool(step.get("done"))), step["position"]))
        for scope in ORDERED_LISTS:
            incoming = sorted((item for item in task_order if item["scope"] == scope and item["task_id"] in added),
                              key=lambda item: item["position"])
            offset = store.db.execute("SELECT COALESCE(MAX(position),-1)+1 FROM task_order WHERE scope=?", (scope,)).fetchone()[0]
            for position, item in enumerate(incoming, offset):
                store.db.execute("INSERT INTO task_order(scope,task_id,position) VALUES (?,?,?)",
                                 (scope, item["task_id"], position))
        for r in reminders:
            cursor = store.db.execute("INSERT OR IGNORE INTO reminders (id,title,notes,weekdays,clock,paused,next_at,snooze_at,deleted_at,created_at,kind,interval,anchor_date,month_day,ordinal,month_weekday,lead_minutes,link,notified_for,expires_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (r["id"], r["title"], r.get("notes", ""), r["weekdays"], r["clock"], int(bool(r.get("paused"))),
                 r["next_at"], r.get("snooze_at"), r.get("deleted_at"), r["created_at"], r["kind"], r["interval"],
                 r["anchor_date"], r["month_day"], r["ordinal"], r["month_weekday"], r["lead_minutes"], r["link"], r["notified_for"], r["expires_at"]))
            count += cursor.rowcount
        for template in templates:
            cursor = store.db.execute("INSERT OR IGNORE INTO templates VALUES (?,?,?,?,?,?)",
                (template["id"], template["name"], template["title"], template.get("notes", ""), template["steps"], template["created_at"]))
            count += cursor.rowcount
    return count
