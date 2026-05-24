import json
import re
from dataclasses import dataclass

import httpx

from .sources import Message


@dataclass
class Classification:
    label: str
    reason: str
    suggested_reply: str | None
    forward_to: str | None
    forward_note: str | None


SYSTEM_PROMPT = """You are an email triage assistant. Classify each email and reply with ONLY a JSON object:
{{
  "label": "ACTION_REQUIRED" | "FYI" | "NEWSLETTER" | "IGNORE",
  "reason": "one sentence",
  "suggested_reply": "short ready-to-send reply, or null",
  "forward_to": "email address if this should be forwarded, or null",
  "forward_note": "note to the recipient if forwarding, or null"
}}

Label definitions — apply strictly:
- ACTION_REQUIRED: a real person is directly asking YOU to do something, reply, decide, or take action. Must be a human sender with a specific request addressed to you personally.
- FYI: informational, no reply needed. A real person sharing something relevant but not requesting action.
- NEWSLETTER: any marketing email, bulk mailing, automated notification, discount offer, product update, or subscription content — regardless of whether it contains a call to action.
- IGNORE: automated system messages, receipts, confirmations, alerts from services, social media notifications, or anything else that needs no attention.

A link to click, an offer to redeem, or a reminder from a service is NEVER ACTION_REQUIRED.
Security alerts from Google/Apple/banks are IGNORE unless you have specific reason to believe they are unexpected.
{extra}"""


class Classifier:
    def __init__(self, config: dict) -> None:
        self.backend = config.get("backend", "ollama")
        self.config = config

    def _call_ollama(self, messages: list[dict]) -> str:
        cfg = self.config["ollama"]
        r = httpx.post(
            f"{cfg['url'].rstrip('/')}/api/chat",
            timeout=60,
            json={"model": cfg["model"], "stream": False, "messages": messages},
        )
        r.raise_for_status()
        return r.json()["message"]["content"]

    def _call_cloudflare(self, messages: list[dict]) -> str:
        cfg = self.config["cloudflare"]
        url = f"https://api.cloudflare.com/client/v4/accounts/{cfg['account_id']}/ai/v1/chat/completions"
        r = httpx.post(
            url,
            timeout=60,
            headers={"Authorization": f"Bearer {cfg['api_token']}"},
            json={"model": cfg["model"], "stream": False, "messages": messages},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def classify(
        self,
        message: Message,
        vip_note: str | None = None,
        routing_context: str | None = None,
    ) -> Classification:
        extra_lines = []
        if vip_note:
            extra_lines.append(f"VIP NOTE: {vip_note}")
        if routing_context:
            extra_lines.append(f"ROUTING: {routing_context}")
        extra = "\n".join(extra_lines)

        system = SYSTEM_PROMPT.format(extra=extra).strip()
        user = f"From: {message.sender}\nSubject: {message.subject}\nSnippet: {message.snippet}"
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        if self.backend == "cloudflare":
            text = self._call_cloudflare(messages)
        else:
            text = self._call_ollama(messages)

        # extract the first {...} block in case the model adds surrounding text
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return Classification(label="IGNORE", reason="Failed to parse model response", suggested_reply=None, forward_to=None, forward_note=None)

        data = json.loads(match.group())
        return Classification(
            label=data.get("label", "IGNORE"),
            reason=data.get("reason", ""),
            suggested_reply=data.get("suggested_reply"),
            forward_to=data.get("forward_to"),
            forward_note=data.get("forward_note"),
        )

    def summarize(self, day: str, items: list) -> str:
        if not items:
            return "Quiet day — nothing landed in your inbox or todo list."

        lines = []
        for item in items:
            status = "done" if item.done else "open"
            who = f" from {item.sender}" if item.sender else ""
            lines.append(f"- [{item.label}] ({status}) {item.title}{who}")
        rundown = "\n".join(lines)

        system = (
            "You write a short end-of-day recap of someone's email-based todo list. "
            "Write 2-4 sentences of plain prose, addressed to the user as 'you'. "
            "Say what was handled today, what action items carry into tomorrow "
            "(open ACTION_REQUIRED or manual items), and call out anything notable. "
            "No JSON, no bullet points, no preamble — just the recap."
        )
        user = f"Date: {day}\n\nItems:\n{rundown}"
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        if self.backend == "cloudflare":
            text = self._call_cloudflare(messages)
        else:
            text = self._call_ollama(messages)
        return text.strip()
