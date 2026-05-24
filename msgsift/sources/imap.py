import email
import subprocess
from datetime import datetime, timezone

from imapclient import IMAPClient

from . import Message, MessageSource


class IMAPSource(MessageSource):
    def __init__(self, config: dict) -> None:
        self.config = config
        self.name = config.get("name", "imap")

    def _password(self) -> str:
        if "password" in self.config:
            return self.config["password"]
        cmd = self.config["password_cmd"]
        return subprocess.check_output(cmd, shell=True).decode().strip()

    def fetch(self) -> list[Message]:
        cfg = self.config
        with IMAPClient(cfg["host"], port=cfg.get("port", 993), ssl=True) as client:
            client.login(cfg["user"], self._password())
            client.select_folder("INBOX")
            uids = client.search(["UNSEEN"])
            uids = uids[-cfg.get("max_emails", 20):]

            if not uids:
                return []

            messages = []
            raw = client.fetch(uids, [b"BODY.PEEK[]", "INTERNALDATE"])
            for uid, data in raw.items():
                msg = email.message_from_bytes(data[b"BODY[]"])
                sender = msg.get("From", "")
                subject = msg.get("Subject", "")
                snippet = _extract_snippet(msg)
                ts = data.get(b"INTERNALDATE") or datetime.now(timezone.utc)
                messages.append(Message(
                    id=str(uid),
                    source=f"imap:{self.name}",
                    sender=sender,
                    subject=subject,
                    snippet=snippet,
                    timestamp=ts,
                ))
            return messages


def _extract_snippet(msg: email.message.Message) -> str:
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                body = part.get_payload(decode=True).decode(errors="replace")
                break
    else:
        body = msg.get_payload(decode=True).decode(errors="replace")
    return body[:300].strip()
