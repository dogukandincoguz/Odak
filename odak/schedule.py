"""Türkçe tarih önerileri ve geçmiş oluşturmayan haftalık takvim."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta

DAYS = ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")
DAY_SHORTS = ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")


@dataclass(frozen=True)
class DateSuggestion:
    title: str
    deadline: datetime
    has_time: bool


def next_occurrence(weekdays: tuple[int, ...] | list[int], clock: str,
                    after: datetime | None = None) -> datetime:
    after = after or datetime.now()
    if not weekdays or any(type(day) is not int or day not in range(7) for day in weekdays):
        raise ValueError("En az bir geçerli tekrar günü seç.")
    hour, minute = map(int, clock.split(":"))
    at = time(hour, minute)
    for offset in range(8):
        day = after.date() + timedelta(days=offset)
        candidate = datetime.combine(day, at)
        if day.weekday() in weekdays and candidate > after:
            return candidate
    raise ValueError("Sonraki tekrar hesaplanamadı.")


def suggest_date(text: str, now: datetime | None = None) -> DateSuggestion | None:
    now = now or datetime.now()
    normalized = text.replace("I", "ı").replace("İ", "i").casefold()
    day = None
    spans = []
    explicit = re.search(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b", normalized)
    if explicit:
        try:
            day = datetime(int(explicit[3]), int(explicit[2]), int(explicit[1])).date()
        except ValueError:
            return None
        spans.append(explicit.span())
    else:
        relative = re.search(r"\b(\d{1,3})\s+gün\s+sonra\b", normalized)
        if relative:
            day = now.date() + timedelta(days=int(relative[1]))
            spans.append(relative.span())
        else:
            words = re.search(r"\b(öbür\s+gün|bugün|yarın|pazartesi|salı|çarşamba|perşembe|cuma|cumartesi|pazar)\b", normalized)
            if words:
                value = words[1]
                if value in ("bugün", "yarın") or value.startswith("öbür"):
                    offset = 0 if value == "bugün" else 1 if value == "yarın" else 2
                else:
                    weekday = [d.casefold() for d in DAYS].index(value)
                    offset = (weekday - now.weekday()) % 7
                day = now.date() + timedelta(days=offset)
                spans.append(words.span())
    # Tarih içindeki rakamları saat diye yorumlama.
    times = list(re.finditer(r"(?<![\d./:])(?:saat\s+)?([01]?\d|2[0-3])[:.]([0-5]\d)(?![\d./:])", normalized))
    clock = next((m for m in times if not any(a <= m.start() < b for a, b in spans)), None)
    if day is None and clock is None:
        return None
    if clock:
        spans.append(clock.span())
    deadline = datetime.combine(day or now.date(), time(int(clock[1]), int(clock[2])) if clock else time(23, 59))
    remainder = text
    for start, end in sorted(spans, reverse=True):
        remainder = remainder[:start] + remainder[end:]
    remainder = re.sub(r"\s+", " ", remainder).strip(" ,;–-")
    if not remainder:
        return None
    return DateSuggestion(remainder, deadline, clock is not None)
