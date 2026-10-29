# timing. A wait skill for AI agents

A small, dependency-free tool that lets **any AI agent with shell or Python access** wait for a precise amount of time (milliseconds to hours) or **until a specific clock time**.

Language-model agents have no sense of time passing between tool calls. Any real delay has to be produced by running code. `timing` gives agents a single, predictable command for that, plus instructions on when and how to use it.

It ships in the [Agent Skills](https://docs.claude.com) `SKILL.md` format, but the script and the guidance work with any agent framework.

## Use cases

- "Wait 30 seconds, then check again"
- Retrying after a rate-limit error (HTTP 429)
- Polling a build, deploy or job until it finishes
- Giving a server time to start before running tests
- Spacing out API requests
- Running an action at a specific time ("at 14:30, do X")

## Quick start

```bash
python3 timing/scripts/wait.py 2m30s
```

```
Waiting 2m30s (started 14:02:10)
... 2m00s remaining
...
DONE elapsed=150.000s (finished 14:04:40)
```

The final `DONE elapsed=…` line gives the agent proof that the wait actually happened.

## Installation

### Agents that support `SKILL.md` skills (e.g. Claude)

- **Claude.ai / Claude app:** upload `timing.skill` from [Releases](../../releases) in the Skills section of settings.
- **Claude Code:** copy the folder into your personal skills directory:

  ```bash
  git clone https://github.com/LAMASE/timing-skill.git
  cp -r timing-skill/timing ~/.claude/skills/
  ```

### Any other agent

1. Place `timing/scripts/wait.py` somewhere the agent can execute it.
2. Make the agent aware of it, using whatever mechanism your framework provides:
   - add the body of `timing/SKILL.md` to the system prompt, an `AGENTS.md` file or a rules file, **or**
   - register `wait.py` as a tool/function the agent can call (see [Using as a tool](#using-as-a-tool)).
3. Adjust the paths in the instructions to match where you put the script.

## Usage

### Chatting with your agent
- "Wait 30 seconds, then check again"
- Retrying after a rate-limit error (HTTP 429)
- Polling a build, deploy or job until it finishes
- Giving a server time to start before running tests
- Spacing out API requests
- Running an action at a specific time ("at 14:30, do X")


### Command line

```bash
python3 scripts/wait.py 30               # 30 seconds (bare number = seconds)
python3 scripts/wait.py 250ms            # 250 milliseconds
python3 scripts/wait.py 2m30s            # compound durations
python3 scripts/wait.py "1.5 hours"      # long-form units
python3 scripts/wait.py --until 14:30    # until the next 14:30 (local machine time)
python3 scripts/wait.py --until 2026-11-01T09:00:00
python3 scripts/wait.py 10 --quiet       # no progress output
```

Supported units: `ms`, `s`/`sec`/`seconds`, `m`/`min`/`minutes`, `h`/`hr`/`hours`, `d`/`days`.

### Python

```python
import sys
sys.path.insert(0, "timing/scripts")
from wait import wait

wait("45s")   # or wait(45)
```

`wait()` returns the remaining seconds (`0.0` when the wait completed).

### Using as a tool

For function-calling agents, expose a thin wrapper. A generic JSON Schema definition:

```json
{
  "name": "wait",
  "description": "Pause for a duration (e.g. '30s', '2m30s', '250ms') or until a clock time. Use before re-checking a job, after rate limits, or between polling attempts. For waits over ~4 minutes, pass max_chunk and call again with the remaining time.",
  "parameters": {
    "type": "object",
    "properties": {
      "duration":  { "type": "string", "description": "e.g. '30', '1.5s', '2m30s', '1h'" },
      "until":     { "type": "string", "description": "HH:MM[:SS] or ISO datetime; alternative to duration" },
      "max_chunk": { "type": "number", "description": "Max seconds to wait in this call" }
    }
  }
}
```

Map the call to `python3 wait.py <duration> [--until …] [--max-chunk …]` and return stdout plus the exit code to the agent.

### Options

| Option | Description |
|---|---|
| `duration` | Time to wait (e.g. `30`, `1.5s`, `2m30s`, `1h`) |
| `--until` | Clock time (`HH:MM[:SS]`) or ISO datetime to wait until |
| `--max-chunk N` | Wait at most `N` seconds in this call |
| `--quiet` | Suppress progress messages |

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Wait completed (`DONE elapsed=…`) |
| `2` | Invalid input (e.g. unknown unit) — fix the input, don't retry blindly |
| `3` | `--max-chunk` limit reached; prints `REMAINING=<seconds>` |

## Long waits and tool timeouts

Most agent runtimes kill shell/tool calls after a timeout, often just a few minutes. A single 20-minute wait would be cut off and the wait lost. For anything longer than ~4 minutes, wait in chunks:

```bash
python3 scripts/wait.py 20m --max-chunk 240
# CHUNK_DONE elapsed=240.000s REMAINING=960.000   (exit 3)
python3 scripts/wait.py 960s --max-chunk 240
# ... repeat until DONE
```

Set `--max-chunk` to about 80% of your runtime's actual timeout.

## Recommended patterns

**Polling with an attempt cap** — better than one long blind wait, because it finishes as soon as the condition is met:

```bash
for i in $(seq 1 20); do
  curl -sf http://localhost:8000/health && break
  python3 scripts/wait.py 5s --quiet
done
```

Always cap attempts so a stuck condition can't loop forever, and have the agent report when the cap is reached.

**Exponential backoff** — double the wait on each attempt (1s, 2s, 4s, 8s…) up to a ceiling. If the server sends a `Retry-After` header, wait exactly that long instead.

## Why Python instead of `sleep`?

| | bash `sleep` | `wait.py` |
|---|---|---|
| Same syntax on Linux / macOS / BusyBox | ❌ | ✅ |
| Compound durations (`2m30s`) | GNU only | ✅ |
| Wait until a clock time | ❌ | ✅ |
| Progress output and measured elapsed time | ❌ | ✅ |
| Chunked waits for tool timeouts | ❌ | ✅ |
| Machine-readable result (exit codes) | Partial | ✅ |
| Dependencies | None | Python 3, standard library only |

For a short fixed pause `sleep` is perfectly fine. `timing` is for when portability, verifiability and long waits matter — which is most of the time in agent workflows.

## Repository layout

```
.
├── README.md
└── timing/
    ├── SKILL.md          # agent instructions and trigger description
    └── scripts/
        └── wait.py       # wait helper (CLI + importable function)
```

## Requirements

- Python 3.7+ (no external dependencies)
- An agent that can run shell commands or call a registered tool

## Known limitations

- **Time zones:** `--until` uses the machine's local clock, which is often UTC on servers. Check with `date` before scheduling, and convert if the user means a different zone.
- **Precision:** `time.sleep()` is accurate to roughly a millisecond; not suitable for sub-millisecond timing.
- **Very long waits:** for waits of hours, a cron job or scheduled task is a better fit than an agent sitting idle — and cheaper, since idle sessions still consume resources.
- **Cost of idle time:** an agent that waits still holds its session open. Prefer polling over fixed waits whenever there's a condition to check.

## Contributing

Issues and pull requests are welcome. Before opening a PR, check that the basics still work:

```bash
python3 timing/scripts/wait.py 250ms
python3 timing/scripts/wait.py 5s --max-chunk 2 --quiet; echo "exit=$?"   # expected: 3
python3 timing/scripts/wait.py 5parsecs; echo "exit=$?"                   # expected: 2
```

## License

MIT

