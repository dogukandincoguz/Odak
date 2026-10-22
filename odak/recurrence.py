"""Tek kayıt üzerinde ilerleyen günlük, haftalık ve aylık programlar."""
from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta
from urllib.parse import urlsplit

from .schedule import DAY_SHORTS

KINDS = ("weekly", "once", "monthly_day", "monthly_weekday")
LEADS = (0, 5, 10, 30)


def meeting_link(value: str) -> str:
    value = value.strip()
    if value:
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.hostname or any(c.isspace() for c in value):
            raise ValueError("Toplantı bağlantısı https:// veya http:// ile başlamalı.")
    return value


def validate_rule(kind, weekdays, clock, anchor, interval=1, month_day=1, ordinal=-1, month_weekday=4):
    if kind not in KINDS:
        raise ValueError("Geçerli bir tekrar türü seç.")
    if type(interval) is not int or not 1 <= interval <= 52:
        raise ValueError("Tekrar aralığı 1–52 arasında olmalı.")
    if not isinstance(anchor, date) or isinstance(anchor, datetime):
        raise ValueError("Geçerli bir başlangıç tarihi seç.")
    if not isinstance(clock, str) or len(clock) != 5 or clock[2] != ":":
        raise ValueError("Geçerli bir saat seç.")
    time.fromisoformat(clock)
    if not isinstance(weekdays, (tuple, list)) or any(type(d) is not int or d not in range(7) for d in weekdays):
        raise ValueError("Tekrar günleri geçersiz.")
    if kind == "weekly" and not weekdays:
        raise ValueError("En az bir tekrar günü seç.")
    if type(month_day) is not int or month_day not in range(32):
        raise ValueError("Ayın günü 1–31 veya son gün olmalı.")
    if type(ordinal) is not int or ordinal not in (1, 2, 3, 4, -1):
        raise ValueError("Ay içindeki tekrar sırası geçersiz.")
    if type(month_weekday) is not int or month_weekday not in range(7):
        raise ValueError("Haftanın günü geçersiz.")


def next_scheduled(kind: str, weekdays, clock: str, anchor: date, interval=1,
                   month_day=1, ordinal=-1, month_weekday=4,
                   after: datetime | None = None) -> datetime | None:
    validate_rule(kind, weekdays, clock, anchor, interval, month_day, ordinal, month_weekday)
    after = after or datetime.now()
    at = time.fromisoformat(clock)
    if kind == "once":
        candidate = datetime.combine(anchor, at)
        return candidate if candidate > after else None
    if kind == "weekly":
        start = max(anchor, after.date())
        anchor_week = anchor - timedelta(days=anchor.weekday())
        for offset in range(interval * 7 + 8):
            day = start + timedelta(days=offset)
            week = (day - anchor_week).days // 7
            candidate = datetime.combine(day, at)
            if week % interval == 0 and day.weekday() in weekdays and candidate > after:
                return candidate
    else:
        start = max(anchor, after.date())
        first = start.year * 12 + start.month - 1
        base = anchor.year * 12 + anchor.month - 1
        # Ayın 31'i gibi seçimlerde bulunmayan aylar atlanır.
        for offset in range(interval * 12 + 13):
            index = first + offset
            if (index - base) % interval:
                continue
            year, month = divmod(index, 12)
            month += 1
            last = calendar.monthrange(year, month)[1]
            if kind == "monthly_day":
                number = month_day or last
                if number > last:
                    continue
            elif ordinal == -1:
                number = last - (date(year, month, last).weekday() - month_weekday) % 7
            else:
                number = 1 + (month_weekday - date(year, month, 1).weekday()) % 7 + (ordinal - 1) * 7
            day = date(year, month, number)
            candidate = datetime.combine(day, at)
            if day >= anchor and candidate > after:
                return candidate
    raise ValueError("Sonraki tekrar hesaplanamadı.")


def rule_label(reminder) -> str:
    if reminder.kind == "once":
        return "Bir kez · " + reminder.anchor_date.strftime("%d.%m.%Y") + " · " + reminder.clock
    if reminder.kind == "weekly":
        days = "Her gün" if len(reminder.weekdays) == 7 else "Hafta içi" if reminder.weekdays == tuple(range(5)) else ", ".join(DAY_SHORTS[d] for d in reminder.weekdays)
        prefix = f"{reminder.interval} haftada bir · " if reminder.interval > 1 else ""
        return prefix + days + " · " + reminder.clock
    prefix = "Her ay" if reminder.interval == 1 else f"{reminder.interval} ayda bir"
    if reminder.kind == "monthly_day":
        day = "son gün" if reminder.month_day == 0 else f"{reminder.month_day}. gün"
    else:
        order = "son" if reminder.ordinal == -1 else f"{reminder.ordinal}."
        day = order + " " + DAY_SHORTS[reminder.month_weekday]
    return f"{prefix} · {day} · {reminder.clock}"
