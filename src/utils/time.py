"""Human-readable formatting of ISO 8601 timestamps."""

from datetime import datetime, timedelta


def format_timestamp(iso_str: str, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """Format an ISO 8601 string (e.g. ``'2026-10-24T10:30:43.756Z'``) as a clean date string.

    Args:
        iso_str: ISO 8601 timestamp; a trailing ``Z`` is accepted.
        fmt: ``strftime`` format for the result.

    Returns:
        The formatted timestamp, or ``""`` if ``iso_str`` is empty.

    Raises:
        ValueError: If ``iso_str`` is not a valid ISO 8601 timestamp.
    """
    if not iso_str:
        return ""

    # Replace 'Z' with +00:00 for Python 3.11+ datetime.fromisoformat compatibility
    clean_iso = iso_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(clean_iso)

    return dt.strftime(fmt)

def parse_time_str(time_str: str) -> timedelta:
    """Convert ``H:MM:SS`` or ``D days, H:MM:SS`` into a timedelta.

    Args:
        time_str: Duration text as produced by ``str(timedelta)``. Fractional seconds are not supported.

    Returns:
        The equivalent timedelta.

    Raises:
        ValueError: If the text does not match the expected format.
    """
    time_str = time_str.strip()
    days = 0
    if " day" in time_str:
        # str(timedelta) renders spans over a day as "2 days, 3:04:05" (or "1 day, ...").
        day_part, time_str = time_str.split(", ", 1)
        days = int(day_part.split()[0])
    hours, minutes, seconds = map(int, time_str.split(":"))
    return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)

def calculate_duration(start_time: str, end_time: str) -> timedelta:
    """Return the time between two ISO 8601 timestamps, truncated to whole seconds.

    Args:
        start_time: Start timestamp (``datetime.fromisoformat`` format).
        end_time: End timestamp in the same format; both must be naive or both timezone-aware.

    Returns:
        ``end_time - start_time`` without microseconds.

    Raises:
        ValueError: If either timestamp is not valid ISO 8601.
        TypeError: If one timestamp is timezone-aware and the other is not.
    """
    dt_start = datetime.fromisoformat(start_time)
    dt_end = datetime.fromisoformat(end_time)

    duration = dt_end - dt_start
    # Remove microseconds from the timedelta object
    return duration - timedelta(microseconds=duration.microseconds)