import sys

from . import store
from .classifier import Classifier
from .config import load_config
from .digest import write_digest
from .sources import Message, MessageSource
from .sources.imap import IMAPSource


def _build_sources(config: dict) -> list[MessageSource]:
    sources: list[MessageSource] = []
    sources_cfg = config.get("sources", {})
    passwords = config.get("imap_passwords", {})
    for account in sources_cfg.get("imap", []):
        if not account.get("enabled"):
            continue
        account = dict(account)
        name = account.get("name", "imap")
        if "password" not in account and name in passwords:
            account["password"] = passwords[name]
        sources.append(IMAPSource(account))
    return sources


def _match_vip(sender: str, vips: list[dict]) -> str | None:
    sender_lower = sender.lower()
    for vip in vips:
        if "email" in vip and vip["email"].lower() in sender_lower:
            return vip.get("note", f"VIP: {vip['email']}")
        if "domain" in vip and sender_lower.endswith("@" + vip["domain"].lower()):
            return vip.get("note", f"VIP domain: {vip['domain']}")
    return None


def _match_rules(msg: Message, rules: list[dict]) -> str | None:
    text = (msg.subject + " " + msg.snippet).lower()
    for rule in rules:
        if any(kw.lower() in text for kw in rule.get("if_contains", [])):
            return f"Forward to {rule['forward_to']}: {rule.get('job_description', '')}"
    return None


def main() -> None:
    config = load_config()
    sources = _build_sources(config)
    classifier = Classifier(config["classifier"])
    vips = config.get("vip", [])
    rules = config.get("routing", {}).get("rules", [])

    messages = [m for source in sources for m in source.fetch()]

    if not messages:
        print("No unread messages.")
        return

    conn = store.connect(config)
    results = []
    for msg in messages:
        # Skip emails already classified and stored — avoids re-burning LLM
        # quota on the same persistent unread mails each run.
        if store.item_exists(conn, msg.source, msg.id):
            continue
        vip_note = _match_vip(msg.sender, vips)
        routing_ctx = _match_rules(msg, rules)
        try:
            classification = classifier.classify(msg, vip_note, routing_ctx)
        except Exception as e:
            print(f"classify failed for {msg.source} {msg.id}: {e}", file=sys.stderr)
            continue
        if vip_note:
            classification.label = "ACTION_REQUIRED"
        store.upsert_email(conn, msg, classification)
        results.append((msg, classification))
    conn.close()

    if results:
        write_digest(results, config)


if __name__ == "__main__":
    main()
