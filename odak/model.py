from __future__ import annotations

import math
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time
from pathlib import Path

from .schedule import next_occurrence

UNDO_SECONDS = 10 * 60


@dataclass(frozen=True)
class Step:
    id: str
    title: str
    done: bool


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    notes: str
    deadline: datetime | None
    has_time: bool
    completed_at: float | None
    deleted_at: float | None
    created_at: float
    today: str | None = None
    someday: bool = False
    steps: tuple[Step, ...] = ()


@dataclass(frozen=True)
class Reminder:
    id: str
    title: str
    notes: str
    weekdays: tuple[int, ...]
    clock: str
    paused: bool
    next_at: datetime
    snooze_at: datetime | None
    deleted_at: float | None
    created_at: float


def make_deadline(day: date | None, clock: datetime_time | None,
                  today: date | None = None) -> datetime | None:
    if day is None and clock is None:
        return None
    return datetime.combine(day or today or date.today(), clock or datetime_time(23, 59))


def category(task: Task, now: datetime | None = None) -> str:
    if task.deleted_at is not None:
        return "trash"
    if task.completed_at is not None:
        return "done"
    if task.someday:
        return "someday"
    if task.deadline is None:
        return "neutral"
    seconds = (task.deadline - (now or datetime.now())).total_seconds()
    if seconds <= 0:
        return "overdue"
    if seconds < 86400:
        return "urgent"
    if seconds <= 3 * 86400:
        return "soon"
    return "neutral"


def time_label(task: Task, now: datetime | None = None) -> str:
    if task.deadline is None:
        return "Deadline yok"
    seconds = (task.deadline - (now or datetime.now())).total_seconds()
    past = seconds <= 0
    minutes = max(1, math.ceil(abs(seconds) / 60))
    if minutes < 60:
        text = f"{minutes} dk"
    elif minutes < 1440:
        hours, mins = divmod(minutes, 60)
        text = f"{hours} sa" + (f" {mins} dk" if mins else "")
    else:
        days, hours = divmod(minutes // 60, 24)
        text = f"{days} gün" + (f" {hours} sa" if hours else "")
    return text + (" geçti" if past else " kaldı")


class Store:
    def __init__(self, path: Path):
        self.path = path.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.ensure_schema()

    def ensure_schema(self):
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL CHECK(length(trim(title)) > 0),
                notes TEXT NOT NULL DEFAULT '',
                deadline TEXT,
                has_time INTEGER NOT NULL DEFAULT 0,
                completed_at REAL,
                deleted_at REAL,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS tasks_deleted ON tasks(deleted_at);
            CREATE TABLE IF NOT EXISTS steps (
                id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                title TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0, position INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS steps_task ON steps(task_id);
            CREATE TABLE IF NOT EXISTS reminders (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
                weekdays TEXT NOT NULL, clock TEXT NOT NULL, paused INTEGER NOT NULL DEFAULT 0,
                next_at TEXT NOT NULL, snooze_at TEXT, deleted_at REAL, created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(tasks)")}
        with self.db:
            if "today" not in columns:
                self.db.execute("ALTER TABLE tasks ADD COLUMN today TEXT")
            if "someday" not in columns:
                self.db.execute("ALTER TABLE tasks ADD COLUMN someday INTEGER NOT NULL DEFAULT 0")

    def save(self, title: str, notes: str = "", deadline: datetime | None = None,
             has_time: bool = False, task_id: str | None = None,
             steps: list[str] | None = None, someday: bool | None = None,
             today: bool | None = None) -> str:
        title = title.strip()
        if not title:
            raise ValueError("Görev başlığı boş olamaz.")
        if len(title) > 180:
            raise ValueError("Görev başlığı en fazla 180 karakter olabilir.")
        if steps is not None and any(len(s.strip()) > 180 for s in steps):
            raise ValueError("Her alt adım en fazla 180 karakter olabilir.")
        values = (title, notes.strip(), deadline.isoformat() if deadline else None,
                  int(has_time and deadline is not None))
        with self.db:
            if task_id:
                self.db.execute(
                    "UPDATE tasks SET title=?,notes=?,deadline=?,has_time=? WHERE id=? AND deleted_at IS NULL",
                    (*values, task_id))
            else:
                task_id = uuid.uuid4().hex
                self.db.execute(
                    "INSERT INTO tasks (title,notes,deadline,has_time,id,created_at) VALUES (?,?,?,?,?,?)",
                    (*values, task_id, time.time()))
            if someday is not None:
                self.db.execute("UPDATE tasks SET someday=?,today=CASE WHEN ? THEN NULL ELSE today END WHERE id=?",
                                (int(someday), int(someday), task_id))
            if today is not None:
                self.db.execute("UPDATE tasks SET today=CASE WHEN someday=0 THEN ? ELSE NULL END WHERE id=?",
                                (date.today().isoformat() if today else None, task_id))
            if steps is not None:
                old_steps = list(self.db.execute("SELECT * FROM steps WHERE task_id=? ORDER BY position", (task_id,)))
                self.db.execute("DELETE FROM steps WHERE task_id=?", (task_id,))
                for position, step_title in enumerate(s.strip() for s in steps if s.strip()):
                    match = next((s for s in old_steps if s["title"] == step_title), None)
                    identity = match["id"] if match else uuid.uuid4().hex
                    if match:
                        old_steps.remove(match)
                    self.db.execute("INSERT INTO steps VALUES (?,?,?,?,?)",
                        (identity, task_id, step_title, match["done"] if match else 0, position))
        return task_id

    def all(self, now: float | None = None) -> list[Task]:
        self.purge(now)
        rows = self.db.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
        steps: dict[str, list[Step]] = {}
        for r in self.db.execute("SELECT * FROM steps ORDER BY position"):
            steps.setdefault(r["task_id"], []).append(Step(r["id"], r["title"], bool(r["done"])))
        return [Task(id=r["id"], title=r["title"], notes=r["notes"],
                     deadline=datetime.fromisoformat(r["deadline"]) if r["deadline"] else None,
                     has_time=bool(r["has_time"]), completed_at=r["completed_at"],
                     deleted_at=r["deleted_at"], created_at=r["created_at"],
                     today=r["today"], someday=bool(r["someday"]),
                     steps=tuple(steps.get(r["id"], ()))) for r in rows]

    def set_today(self, task_id: str, selected: bool):
        with self.db:
            self.db.execute("UPDATE tasks SET today=?,someday=CASE WHEN ? THEN 0 ELSE someday END WHERE id=?",
                            (date.today().isoformat() if selected else None, int(selected), task_id))

    def set_someday(self, task_id: str, selected: bool):
        with self.db:
            self.db.execute("UPDATE tasks SET someday=?,today=NULL WHERE id=?", (int(selected), task_id))

    def set_step(self, step_id: str, done: bool):
        with self.db:
            self.db.execute("UPDATE steps SET done=? WHERE id=?", (int(done), step_id))

    def complete(self, task_id: str, completed: bool):
        with self.db:
            self.db.execute("UPDATE tasks SET completed_at=? WHERE id=? AND deleted_at IS NULL",
                            (time.time() if completed else None, task_id))

    def delete(self, task_id: str, now: float | None = None):
        with self.db:
            self.db.execute("UPDATE tasks SET deleted_at=? WHERE id=? AND deleted_at IS NULL",
                            (time.time() if now is None else now, task_id))

    def restore(self, task_id: str, now: float | None = None) -> bool:
        stamp = time.time() if now is None else now
        with self.db:
            result = self.db.execute(
                "UPDATE tasks SET deleted_at=NULL WHERE id=? AND deleted_at>?",
                (task_id, stamp - UNDO_SECONDS))
        return result.rowcount > 0

    def purge(self, now: float | None = None):
        stamp = time.time() if now is None else now
        with self.db:
            self.db.execute("DELETE FROM tasks WHERE deleted_at IS NOT NULL AND deleted_at<=?",
                            (stamp - UNDO_SECONDS,))
            self.db.execute("DELETE FROM reminders WHERE deleted_at IS NOT NULL AND deleted_at<=?",
                            (stamp - UNDO_SECONDS,))

    def save_reminder(self, title: str, notes: str, weekdays: list[int], clock: str,
                      reminder_id: str | None = None, now: datetime | None = None) -> str:
        if not title.strip() or len(title.strip()) > 180:
            raise ValueError("Hatırlatma başlığı 1–180 karakter olmalı.")
        days = sorted(set(weekdays))
        next_at = next_occurrence(days, clock, now)
        with self.db:
            if reminder_id:
                old = self.db.execute("SELECT * FROM reminders WHERE id=? AND deleted_at IS NULL", (reminder_id,)).fetchone()
                if old and json.loads(old["weekdays"]) == days and old["clock"] == clock:
                    self.db.execute("UPDATE reminders SET title=?,notes=? WHERE id=?",
                                    (title.strip(), notes.strip(), reminder_id))
                else:
                    self.db.execute("UPDATE reminders SET title=?,notes=?,weekdays=?,clock=?,next_at=?,snooze_at=NULL WHERE id=? AND deleted_at IS NULL",
                        (title.strip(), notes.strip(), json.dumps(days), clock, next_at.isoformat(), reminder_id))
            else:
                reminder_id = uuid.uuid4().hex
                self.db.execute("INSERT INTO reminders (id,title,notes,weekdays,clock,next_at,created_at) VALUES (?,?,?,?,?,?,?)",
                    (reminder_id, title.strip(), notes.strip(), json.dumps(days), clock, next_at.isoformat(), time.time()))
        return reminder_id

    def reminders(self, now: float | None = None) -> list[Reminder]:
        self.purge(now)
        return [Reminder(r["id"], r["title"], r["notes"], tuple(json.loads(r["weekdays"])), r["clock"],
            bool(r["paused"]), datetime.fromisoformat(r["next_at"]),
            datetime.fromisoformat(r["snooze_at"]) if r["snooze_at"] else None,
            r["deleted_at"], r["created_at"]) for r in self.db.execute("SELECT * FROM reminders ORDER BY next_at")]

    def pause_reminder(self, reminder_id: str, paused: bool, now: datetime | None = None):
        reminder = next(r for r in self.reminders() if r.id == reminder_id)
        next_at = next_occurrence(reminder.weekdays, reminder.clock, now)
        with self.db:
            self.db.execute("UPDATE reminders SET paused=?,next_at=?,snooze_at=NULL WHERE id=?",
                            (int(paused), next_at.isoformat(), reminder_id))

    def skip_reminder(self, reminder_id: str, now: datetime | None = None):
        reminder = next(r for r in self.reminders() if r.id == reminder_id)
        next_at = next_occurrence(reminder.weekdays, reminder.clock, max(now or datetime.now(), reminder.next_at))
        with self.db:
            self.db.execute("UPDATE reminders SET next_at=?,snooze_at=NULL WHERE id=?", (next_at.isoformat(), reminder_id))

    def snooze_reminder(self, reminder_id: str, now: datetime | None = None):
        from datetime import timedelta
        until = (now or datetime.now()) + timedelta(minutes=10)
        with self.db:
            self.db.execute("UPDATE reminders SET snooze_at=? WHERE id=? AND paused=0 AND deleted_at IS NULL",
                            (until.isoformat(), reminder_id))

    def delete_reminder(self, reminder_id: str):
        with self.db:
            self.db.execute("UPDATE reminders SET deleted_at=? WHERE id=?", (time.time(), reminder_id))

    def restore_reminder(self, reminder_id: str) -> bool:
        with self.db:
            result = self.db.execute("UPDATE reminders SET deleted_at=NULL WHERE id=? AND deleted_at>?",
                                    (reminder_id, time.time() - UNDO_SECONDS))
        return result.rowcount > 0

    def due_reminders(self, now: datetime | None = None) -> list[Reminder]:
        now = now or datetime.now()
        due = []
        for r in self.reminders():
            if r.paused or r.deleted_at is not None:
                continue
            scheduled = r.next_at <= now
            snoozed = r.snooze_at is not None and r.snooze_at <= now
            if not scheduled and not snoozed:
                continue
            # Kapalı geçen günlerin bildirimlerini biriktirme.
            fresh = scheduled and (now - r.next_at).total_seconds() <= 900
            fresh |= snoozed and (now - r.snooze_at).total_seconds() <= 900
            if fresh:
                due.append(r)
            with self.db:
                if scheduled:
                    self.db.execute("UPDATE reminders SET next_at=? WHERE id=?",
                        (next_occurrence(r.weekdays, r.clock, now).isoformat(), r.id))
                if snoozed:
                    self.db.execute("UPDATE reminders SET snooze_at=NULL WHERE id=?", (r.id,))
        return due

    def setting(self, key: str, default=None):
        row = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_setting(self, key: str, value):
        encoded = json.dumps(value, ensure_ascii=False)
        with self.db:
            self.db.execute("INSERT INTO settings VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value WHERE settings.value<>excluded.value",
                            (key, encoded))

    def close(self):
        self.db.close()
