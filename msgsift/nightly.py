import sys

from . import store
from .classifier import Classifier
from .config import load_config


def main() -> None:
    config = load_config()
    conn = store.connect(config)
    today = store.today_str()

    # Try to write the day's recap first (so it can see what carries into
    # tomorrow). The LLM call can fail (rate-limit, network) — if it does,
    # log and continue: the rollover below is essential bookkeeping and must
    # always run, otherwise unfinished items get stuck on today forever.
    items = store.items_for_day(conn, today)
    try:
        summary = Classifier(config["classifier"]).summarize(today, items)
        store.set_summary(conn, today, summary)
    except Exception as e:
        print(f"nightly summary failed: {e}", file=sys.stderr)

    store.rollover(conn, today)
    conn.close()
    print(f"Nightly run complete for {today}.")


if __name__ == "__main__":
    main()
