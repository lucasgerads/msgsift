# msgsift

Local-first email triage that turns your inbox into a calendar-style todo list.

`msgsift` fetches your unread mail over IMAP, classifies each message with an LLM
(local [Ollama](https://ollama.com) by default, or Cloudflare Workers AI), and organizes
everything into a per-day todo list with a small web UI. A nightly job writes you a short
recap of the day and rolls unfinished items forward. Your own manual todos live in the same
list. Nothing leaves your machine unless you opt into the Cloudflare backend.

## How it works

- **Classify** every unread email as `ACTION_REQUIRED`, `FYI`, `NEWSLETTER`, or `IGNORE`,
  with a one-line reason and (where useful) a suggested reply.
- **VIP list** — senders (by email or domain) are always forced to `ACTION_REQUIRED`.
- **Forwarding hints** — content rules suggest who to forward something to.
- **Daily rollover** — at end of day, FYIs/newsletters auto-close, unfinished action items
  carry to tomorrow, and finished ones stay (scratched out) as a record of what you did.
- **Nightly recap** — the model writes a couple of sentences summarizing the day.

## Install

```bash
uv tool install msgsift
```

This gives you three commands: `msgsift` (fetch + classify), `msgsift-nightly`
(recap + rollover), and `msgsift-web` (the web UI).

## Configure

Config lives in `~/.config/msgsift/` (override with `MSGSIFT_CONFIG_DIR`):

```bash
mkdir -p ~/.config/msgsift
cp config.example.toml ~/.config/msgsift/config.toml
cp credentials.example.toml ~/.config/msgsift/credentials.toml
# then edit both — config.toml for settings, credentials.toml for secrets
```

`credentials.toml` holds only secrets (IMAP passwords, API tokens) and should never be
committed or shared.

## Run

```bash
msgsift          # fetch unread mail, classify, store, print a digest
msgsift-web      # serve the web UI (default http://127.0.0.1:8000)
msgsift-nightly  # write the day's recap and roll items over
```

Typically `msgsift` runs on a timer through the day, `msgsift-nightly` once at night, and
`msgsift-web` as a long-running service. Example `systemd` user units are in `systemd/`.

## Backends

- **Ollama (default):** fully local and private. Point `[classifier.ollama]` at your Ollama
  server and pull a small model (e.g. `qwen2.5:3b`).
- **Cloudflare Workers AI:** offloads inference to a larger model. Set
  `[classifier]` `backend = "cloudflare"` and provide an `account_id` + `api_token`. Note:
  with this backend, message envelopes (sender, subject, snippet) leave your device.

## License

[AGPL-3.0-or-later](LICENSE).
