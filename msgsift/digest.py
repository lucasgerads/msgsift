from datetime import datetime
from pathlib import Path

from .classifier import Classification
from .sources import Message

LABEL_ORDER = ["ACTION_REQUIRED", "FYI", "NEWSLETTER", "IGNORE"]


def write_digest(results: list[tuple[Message, Classification]], config: dict) -> None:
    lines = _format(results)
    output_cfg = config.get("output", {})
    mode = output_cfg.get("mode", "stdout")

    if mode == "stdout":
        print("\n".join(lines))
    elif mode == "log":
        path = Path(output_cfg["log_path"]).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as f:
            f.write("\n".join(lines) + "\n\n")


def _format(results: list[tuple[Message, Classification]]) -> list[str]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"=== msgsift digest — {now} ===", ""]

    grouped: dict[str, list[tuple[Message, Classification]]] = {label: [] for label in LABEL_ORDER}
    for msg, cls in results:
        grouped.setdefault(cls.label, []).append((msg, cls))

    for label in LABEL_ORDER:
        items = grouped.get(label, [])
        if not items:
            continue

        if label in ("NEWSLETTER", "IGNORE"):
            lines.append(f"{label} ({len(items)} suppressed)")
            lines.append("")
            continue

        lines.append(label)
        for msg, cls in items:
            lines.append(f"  [{msg.sender}] {msg.subject}")
            lines.append(f"  Reason: {cls.reason}")
            if cls.suggested_reply:
                lines.append(f"  Reply:  {cls.suggested_reply}")
            if cls.forward_to:
                note = f" — {cls.forward_note}" if cls.forward_note else ""
                lines.append(f"  Fwd to: {cls.forward_to}{note}")
            lines.append("")

    lines.append("=" * 40)
    return lines
