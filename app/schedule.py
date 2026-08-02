"""Rounds/timings for vendors who don't have a fixed shop.

A thela/cart vendor doesn't sit at one address — they park at a few spots on a
loop ("Gali no. 4 pe har mangalwar 10 se 12"). Each of those spots is a *stop*:
a place plus a weekly (or daily) time window. This module turns a stop's raw
fields into the two things the rest of the app needs — a human sentence for the
card, and "is he there right now / when next", which is what search ranks on.

Times are stored as plain "HH:MM" strings in the vendor's local timezone
(MYNA_TIMEZONE, default Asia/Kolkata) — a thela's schedule is local by
definition, and storing UTC would make the shopkeeper form lie about the hours
they typed in.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .config import TIMEZONE

# 0 = Monday … 6 = Sunday, matching datetime.weekday().
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# day_of_week sentinel for "every day", so a daily vendor doesn't have to add
# seven rows for the same corner.
EVERY_DAY = -1

# Ranking buckets used by search: a vendor standing at the stop right now is
# worth more than one who comes back on Friday, however close that corner is.
AVAILABLE_NOW = 0
LATER_TODAY = 1
ANOTHER_DAY = 2


def tz() -> ZoneInfo:
    try:
        return ZoneInfo(TIMEZONE)
    except Exception:
        return ZoneInfo("Asia/Kolkata")


def now_local() -> datetime:
    return datetime.now(tz())


def parse_hhmm(value: str) -> int | None:
    """"10:00" -> 600 minutes past midnight. Returns None if unusable."""
    if not value:
        return None
    parts = str(value).strip().split(":")
    if len(parts) < 2:
        return None
    try:
        hours, minutes = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        return None
    return hours * 60 + minutes


def format_hhmm(value: str) -> str:
    """"14:30" -> "2:30 PM"; "10:00" -> "10 AM" (drop a bare :00 — nobody says
    "das baje zero minute")."""
    minutes = parse_hhmm(value)
    if minutes is None:
        return ""
    hour24, minute = divmod(minutes, 60)
    suffix = "AM" if hour24 < 12 else "PM"
    hour12 = hour24 % 12 or 12
    return f"{hour12} {suffix}" if minute == 0 else f"{hour12}:{minute:02d} {suffix}"


def day_label(day_of_week: int) -> str:
    if day_of_week is None or day_of_week == EVERY_DAY:
        return "Every day"
    try:
        return f"Every {DAY_NAMES[int(day_of_week)]}"
    except (IndexError, ValueError, TypeError):
        return "Every day"


def window_label(start_time: str, end_time: str) -> str:
    start, end = format_hhmm(start_time), format_hhmm(end_time)
    if start and end:
        return f"{start} – {end}"
    return start or end or "any time"


def describe(day_of_week: int, start_time: str, end_time: str) -> str:
    """"Every Tuesday · 10 AM – 12 PM" — the line printed on the shop card."""
    return f"{day_label(day_of_week)} · {window_label(start_time, end_time)}"


def _minutes_until_next(day_of_week: int, start: int, now: datetime) -> int:
    """Minutes from `now` until the stop's window next opens."""
    now_minutes = now.hour * 60 + now.minute
    if day_of_week is None or day_of_week == EVERY_DAY:
        days_ahead = 0 if start > now_minutes else 1
    else:
        days_ahead = (int(day_of_week) - now.weekday()) % 7
        if days_ahead == 0 and start <= now_minutes:
            days_ahead = 7
    return days_ahead * 24 * 60 + (start - now_minutes)


def status(day_of_week: int, start_time: str, end_time: str, now: datetime | None = None) -> dict:
    """Where this stop stands right now.

    Returns rank (for search ordering), a short status string, and a phrase for
    the card. A stop with no times set is treated as "comes by on that day" —
    the vendor left the hours blank rather than promising a window, so it ranks
    with the rest of that day instead of claiming to be live.
    """
    now = now or now_local()
    start = parse_hhmm(start_time)
    end = parse_hhmm(end_time)
    now_minutes = now.hour * 60 + now.minute
    today = day_of_week is None or day_of_week == EVERY_DAY or int(day_of_week) == now.weekday()

    if start is None:
        if today:
            return {"rank": LATER_TODAY, "status": "today", "status_text": "Comes by today"}
        return {"rank": ANOTHER_DAY, "status": "upcoming",
                "status_text": f"Comes by on {DAY_NAMES[int(day_of_week)]}"}

    if today and start <= now_minutes and (end is None or now_minutes < end):
        text = f"Here now · till {format_hhmm(end_time)}" if end is not None else "Here now"
        return {"rank": AVAILABLE_NOW, "status": "here_now", "status_text": text}

    minutes_away = _minutes_until_next(day_of_week, start, now)
    if minutes_away < 0:  # window ended earlier today
        minutes_away = _minutes_until_next(day_of_week, start, now + timedelta(minutes=1))

    if minutes_away <= 0:
        return {"rank": AVAILABLE_NOW, "status": "here_now", "status_text": "Here now"}

    # Which calendar day the next window falls on decides both the wording and
    # the bucket — "today" has to mean today's date, not merely a stop that
    # also runs today (a daily 7–9 AM round is tomorrow's news by noon).
    target = now + timedelta(minutes=minutes_away)
    window = window_label(start_time, end_time)
    if target.date() == now.date():
        if minutes_away < 60:
            return {"rank": LATER_TODAY, "status": "today",
                    "status_text": f"Here in {minutes_away} min · {format_hhmm(start_time)}"}
        return {"rank": LATER_TODAY, "status": "today", "status_text": f"Today {window}"}
    if target.date() == (now + timedelta(days=1)).date():
        return {"rank": ANOTHER_DAY, "status": "upcoming", "status_text": f"Tomorrow {window}"}
    return {"rank": ANOTHER_DAY, "status": "upcoming",
            "status_text": f"{DAY_SHORT[target.weekday()]} {window}"}


def stop_view(stop, now: datetime | None = None) -> dict:
    """Everything the API returns about one stop: stored fields + the derived
    'when' sentence and live status."""
    info = status(stop.day_of_week, stop.start_time, stop.end_time, now)
    return {
        "stop_id": stop.stop_id,
        "shop_id": stop.shop_id,
        "label": stop.label or "",
        "lat": stop.lat,
        "long": stop.long,
        "address": stop.address or "",
        "day_of_week": stop.day_of_week if stop.day_of_week is not None else EVERY_DAY,
        "start_time": stop.start_time or "",
        "end_time": stop.end_time or "",
        "note": stop.note or "",
        "when": describe(stop.day_of_week, stop.start_time, stop.end_time),
        "status": info["status"],
        "status_text": info["status_text"],
        "rank": info["rank"],
    }
