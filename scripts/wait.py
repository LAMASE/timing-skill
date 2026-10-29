#!/usr/bin/env python3
"""
wait.py - precise, human-friendly waiting for agent workflows.

Usage (CLI):
    python3 wait.py 30            # 30 seconds
    python3 wait.py 1.5s          # 1.5 seconds
    python3 wait.py 2m30s         # 2 minutes 30 seconds
    python3 wait.py 1h            # 1 hour
    python3 wait.py 250ms         # 250 milliseconds
    python3 wait.py --until 14:30 # until next 14:30 local time
    python3 wait.py --until 2026-11-01T09:00:00
    python3 wait.py 5m --max-chunk 240   # wait at most 240s, then report remaining

Usage (import):
    from wait import wait
    wait("2m30s")

Exit codes:
    0  wait completed
    2  invalid input
    3  chunk limit reached; remaining time printed as REMAINING=<seconds>
"""
import argparse
import re
import sys
import time
from datetime import datetime, timedelta

_UNITS = {
    "ms": 0.001,
    "s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
    "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
    "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600,
    "d": 86400, "day": 86400, "days": 86400,
}
_TOKEN = re.compile(r"(\d+(?:\.\d+)?)\s*([a-z]*)")


def parse_duration(text):
    """Turn '2m30s', '90', '1.5 hours', '250ms' into seconds (float)."""
    s = str(text).strip().lower().replace(",", ".")
    if not s:
        raise ValueError("empty duration")
    total, pos = 0.0, 0
    for match in _TOKEN.finditer(s):
        if s[pos:match.start()].strip():
            raise ValueError(f"cannot parse duration: {text!r}")
        value, unit = float(match.group(1)), match.group(2) or "s"
        if unit not in _UNITS:
            raise ValueError(f"unknown unit {unit!r} in {text!r}")
        total += value * _UNITS[unit]
        pos = match.end()
    if pos == 0 or s[pos:].strip():
        raise ValueError(f"cannot parse duration: {text!r}")
    return total


def seconds_until(target):
    """Seconds from now until a clock time ('14:30', '14:30:15') or ISO datetime."""
    now = datetime.now()
    try:
        dt = datetime.fromisoformat(target)
    except ValueError:
        parts = target.split(":")
        if not 2 <= len(parts) <= 3:
            raise ValueError(f"cannot parse time: {target!r}")
        h, m = int(parts[0]), int(parts[1])
        sec = int(parts[2]) if len(parts) == 3 else 0
        dt = now.replace(hour=h, minute=m, second=sec, microsecond=0)
        if dt <= now:
            dt += timedelta(days=1)  # next occurrence
    return max(0.0, (dt - now).total_seconds())


def fmt(seconds):
    seconds = max(0.0, seconds)
    if seconds < 60:
        return f"{seconds:.2f}s" if seconds < 10 else f"{seconds:.0f}s"
    m, s = divmod(int(round(seconds)), 60)
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"


def wait(duration, progress=True, max_chunk=None):
    """
    Block for `duration` (seconds as number, or string like '2m30s').
    Uses a monotonic clock so system clock changes don't affect it.
    Returns remaining seconds (0.0 if fully waited, >0 if max_chunk cut it short).
    """
    total = duration if isinstance(duration, (int, float)) else parse_duration(duration)
    if total < 0:
        raise ValueError("duration must be >= 0")
    budget = total if max_chunk is None else min(total, max_chunk)

    start = time.monotonic()
    deadline = start + budget
    # Progress heartbeat keeps long waits visible; interval scales with length.
    interval = 10 if budget <= 120 else 30 if budget <= 900 else 60
    next_report = start + interval

    while True:
        now = time.monotonic()
        left = deadline - now
        if left <= 0:
            break
        if progress and now >= next_report:
            print(f"... {fmt(total - (now - start))} remaining", flush=True)
            next_report += interval
        time.sleep(min(left, max(0.0, next_report - now), 1.0))

    return max(0.0, total - (time.monotonic() - start))


def main():
    p = argparse.ArgumentParser(description="Wait a specific amount of time.")
    p.add_argument("duration", nargs="?", help="e.g. 30, 1.5s, 2m30s, 1h, 250ms")
    p.add_argument("--until", help="clock time (HH:MM[:SS]) or ISO datetime")
    p.add_argument("--max-chunk", type=float, default=None,
                   help="max seconds to wait in this call (to stay under tool timeouts)")
    p.add_argument("--quiet", action="store_true", help="no progress output")
    a = p.parse_args()

    try:
        if a.until:
            seconds = seconds_until(a.until)
        elif a.duration:
            seconds = parse_duration(a.duration)
        else:
            p.error("give a duration or --until")
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)

    started = datetime.now()
    if not a.quiet:
        print(f"Waiting {fmt(seconds)} (started {started:%H:%M:%S})", flush=True)
    t0 = time.monotonic()
    remaining = wait(seconds, progress=not a.quiet, max_chunk=a.max_chunk)
    elapsed = time.monotonic() - t0

    if remaining > 0.001:
        print(f"CHUNK_DONE elapsed={elapsed:.3f}s REMAINING={remaining:.3f}", flush=True)
        sys.exit(3)
    print(f"DONE elapsed={elapsed:.3f}s (finished {datetime.now():%H:%M:%S})", flush=True)


if __name__ == "__main__":
    main()
