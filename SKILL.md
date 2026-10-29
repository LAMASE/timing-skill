---
name: timing
description: Wait, pause, sleep or delay for a specific amount of time (milliseconds to hours) or until a given clock time, using a bundled Python wait() helper. Use this skill whenever a task needs Claude to wait before continuing — e.g. "wait 30 seconds then check again", "pause 2 minutes", "retry after a delay", backing off after a rate limit (HTTP 429), polling a build/deploy/job until it finishes, giving a server time to start, spacing out requests, or "do X at 14:30". Trigger even if the user doesn't say "wait" explicitly but the workflow clearly needs a timed delay between steps.
---

# Timing

Claude has no internal sense of time passing between tool calls, so any real delay must be produced by running code. This skill provides `scripts/wait.py`, a small Python helper built on `time.sleep()` with a monotonic clock.

**Why Python rather than bash `sleep`:** `sleep` is fine for a quick fixed pause, but its unit syntax differs between GNU/macOS/BusyBox, it can't wait "until 14:30", and it gives no progress output. `wait.py` uses only the standard library, behaves identically everywhere Python 3 runs, accepts human-friendly durations, and reports elapsed time so you can confirm the wait actually happened.

## Quick reference

Run from the skill directory (adjust the path to where the skill is installed):

```bash
python3 scripts/wait.py 30              # 30 seconds (bare number = seconds)
python3 scripts/wait.py 250ms
python3 scripts/wait.py 2m30s
python3 scripts/wait.py "1.5 hours"
python3 scripts/wait.py --until 14:30   # next 14:30, local time of the machine
python3 scripts/wait.py --until 2026-11-01T09:00:00
python3 scripts/wait.py 10 --quiet      # no progress lines
```

Output ends with `DONE elapsed=<seconds>s`. Exit code 2 means the duration couldn't be parsed — fix the input, don't retry blindly.

From Python code:

```python
import sys; sys.path.insert(0, "<skill-dir>/scripts")
from wait import wait
wait("45s")          # or wait(45)
```

## Long waits: stay under the tool timeout

Shell tool calls usually have a timeout (often a few minutes). A single 20-minute sleep will likely be killed mid-way and the wait will be lost. For anything longer than ~4 minutes, wait in chunks:

```bash
python3 scripts/wait.py 20m --max-chunk 240
```

This waits at most 240 seconds, then exits with code 3 and prints `REMAINING=<seconds>`. Call it again with that remaining value (`python3 scripts/wait.py <REMAINING>s --max-chunk 240`) until you get `DONE`. Tell the user briefly that you're waiting in chunks so the silence isn't confusing.

If you know the environment's timeout, set `--max-chunk` to roughly 80% of it.

## Common patterns

**Polling until something is ready** — prefer a check loop with a cap over one long blind wait, because it finishes as soon as the condition is met:

```bash
for i in $(seq 1 20); do
  curl -sf http://localhost:8000/health && break
  python3 scripts/wait.py 5s --quiet
done
```

Always set a maximum number of attempts so a stuck condition can't loop forever, and report to the user if the cap is reached.

**Backoff after rate limits / transient errors** — double the wait each attempt (e.g. 1s, 2s, 4s, 8s…) up to a ceiling; if the server sends a `Retry-After` header, wait exactly that long instead.

**Scheduled action** — `--until HH:MM` uses the machine's local clock, which may be UTC on a server and differ from the user's time zone. Check with `date` first and convert if needed; mention the assumption to the user.

## Guidelines

- Use the shortest wait that does the job; long idle waits consume the user's time and session.
- If the user asks for a wait longer than about an hour, confirm it's really what they want before starting — a scheduled task or a cron job is usually a better tool for that.
- Report the actual elapsed time from the `DONE` line rather than assuming the wait succeeded.
- `time.sleep()` precision is roughly milliseconds; don't rely on it for sub-millisecond timing.