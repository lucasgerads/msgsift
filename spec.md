# msgsift

A lightweight, local-first message triage tool. Fetches messages from configured sources, classifies them using a local LLM via Ollama, and outputs a prioritized digest. Runs as a systemd user timer.

---

## Goals

- Privacy-first: all inference runs locally via Ollama, no data leaves the machine
- Minimal dependencies
- Extensible: email first, other sources (Slack, SMS, etc.) later
- Output is a simple human-readable digest (log file or stdout)

---

## Architecture

```
sources/        # one module per message source (imap, slack, ...)
classifier.py   # sends messages to Ollama, returns labels
digest.py       # formats and outputs the triage result
main.py         # entry point, orchestrates sources → classifier → digest
config.yaml     # user configuration (credentials, model, thresholds)
```

---

## Configuration (`config.toml`)

```toml
model = "qwen3:3b"          # any Ollama model
ollama_url = "http://localhost:11434"

[sources.imap]
enabled = true
host = "imap.gmail.com"
port = 993
user = "lucas@example.com"
password_cmd = "cat ~/.secrets/email_pass"  # shell command to retrieve password
max_emails = 20        # per run, most recent unread

[output]
mode = "log"              # log | stdout | imap_flags
log_path = "~/.local/share/msgsift/digest.log"
```

`password_cmd` runs a shell command to retrieve the password (e.g. `pass email/gmail`, `cat ~/.secrets/...`) — no plaintext passwords in config.

---

## Classification

Each message is reduced to a minimal envelope before sending to the LLM:

```
sender, subject, first 300 chars of body
```

Prompt instructs the model to return only JSON:

```json
{"label": "ACTION_REQUIRED", "reason": "Invoice due Friday"}
```

Labels: `ACTION_REQUIRED` · `FYI` · `NEWSLETTER` · `IGNORE`

The classifier batches messages in a single prompt where possible to reduce Ollama round-trips.

---

## Output (digest)

A plain-text digest written to the log file or stdout:

```
=== msgsift digest — 2026-05-19 14:00 ===

ACTION_REQUIRED
  [client@example.com] Invoice #1042 due Friday
  [bank@sparkasse.de]  Überweisung bestätigen

FYI
  [github@github.com]  PR merged: feature/mcp-server

IGNORE (3 emails suppressed)
=====================================
```

---

## Systemd Integration

Two files in `~/.config/systemd/user/`:

**`msgsift.service`**
```ini
[Unit]
Description=msgsift message triage

[Service]
Type=oneshot
ExecStart=/home/lucas/.venv/bin/python /home/lucas/scripts/msgsift/main.py
StandardOutput=journal
StandardError=journal
```

**`msgsift.timer`**
```ini
[Unit]
Description=Run msgsift every hour

[Timer]
OnBootSec=2min
OnUnitActiveSec=1h

[Install]
WantedBy=timers.target
```

Enable with:
```bash
systemctl --user daemon-reload
systemctl --user enable --now msgsift.timer
```

---

## Source Interface

Each source module implements:

```python
class MessageSource:
    def fetch(self) -> list[Message]:
        ...

@dataclass
class Message:
    id: str
    source: str          # "imap", "slack", etc.
    sender: str
    subject: str
    snippet: str         # first 300 chars of body
    timestamp: datetime
```

Adding a new source = new module in `sources/` implementing this interface.

---

## Tech Stack

- Python 3.11+
- `imapclient` for IMAP
- `httpx` or `requests` for Ollama REST API
- `tomllib` (stdlib, 3.11+) for config
- No LangChain, no heavyweight frameworks
- Packaged with `uv` / `pyproject.toml`

---

## Out of Scope (v1)

- Writing back IMAP flags or moving emails to folders
- A UI or web dashboard
- Multi-account support per source
- Fine-tuning or prompt caching
