from __future__ import annotations

import math
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time
from pathlib import Path

UNDO_SECONDS = 10 * 60


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
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
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
        """)

    def save(self, title: str, notes: str = "", deadline: datetime | None = None,
             has_time: bool = False, task_id: str | None = None) -> str:
        title = title.strip()
        if not title:
            raise ValueError("Görev başlığı boş olamaz.")
        if len(title) > 180:
            raise ValueError("Görev başlığı en fazla 180 karakter olabilir.")
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
        return task_id

    def all(self, now: float | None = None) -> list[Task]:
        self.purge(now)
        rows = self.db.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
        return [Task(id=r["id"], title=r["title"], notes=r["notes"],
                     deadline=datetime.fromisoformat(r["deadline"]) if r["deadline"] else None,
                     has_time=bool(r["has_time"]), completed_at=r["completed_at"],
                     deleted_at=r["deleted_at"], created_at=r["created_at"]) for r in rows]

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

    def close(self):
        self.db.close()
