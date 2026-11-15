"""Canonical UTC timestamps for ordering and configured boundaries."""
from datetime import datetime, timezone


def utc_timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')
