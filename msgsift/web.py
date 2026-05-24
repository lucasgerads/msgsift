from datetime import date, timedelta
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from . import store
from .config import load_config

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="msgsift")
config = load_config()

LABEL_ORDER = ["ACTION_REQUIRED", "FYI", "NEWSLETTER", "IGNORE"]


def _grouped(items: list[store.Item]) -> dict[str, list[store.Item]]:
    grouped: dict[str, list[store.Item]] = {label: [] for label in LABEL_ORDER}
    for item in items:
        grouped.setdefault(item.label or "FYI", []).append(item)
    return {label: grouped[label] for label in LABEL_ORDER if grouped.get(label)}


def _render_day(request: Request, day: str):
    conn = store.connect(config)
    items = store.items_for_day(conn, day)
    summary = store.get_summary(conn, day)
    recent_days = store.list_days(conn)
    conn.close()

    d = date.fromisoformat(day)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "day": day,
            "is_today": day == store.today_str(),
            "prev_day": (d - timedelta(days=1)).isoformat(),
            "next_day": (d + timedelta(days=1)).isoformat(),
            "grouped": _grouped(items),
            "summary": summary,
            "recent_days": recent_days,
        },
    )


@app.get("/")
def index(request: Request):
    return _render_day(request, store.today_str())


@app.get("/day/{day}")
def day_view(request: Request, day: str):
    return _render_day(request, day)


@app.post("/todo")
def add_todo(title: str = Form(...), note: str = Form("")):
    title = title.strip()
    if title:
        conn = store.connect(config)
        store.add_manual_todo(conn, title, note.strip() or None)
        conn.close()
    return RedirectResponse("/", status_code=303)


@app.post("/done/{item_id}")
def mark_done(item_id: int, done: bool = Form(True), day: str = Form("")):
    conn = store.connect(config)
    store.set_done(conn, item_id, done)
    conn.close()
    target = f"/day/{day}" if day else "/"
    return RedirectResponse(target, status_code=303)


def run() -> None:
    import uvicorn

    web_cfg = config.get("web", {})
    uvicorn.run(
        "msgsift.web:app",
        host=web_cfg.get("host", "127.0.0.1"),
        port=web_cfg.get("port", 8000),
    )
