from . import store
from .classifier import Classifier
from .config import load_config


def main() -> None:
    config = load_config()
    conn = store.connect(config)
    today = store.today_str()

    # Summarize before rollover so the recap can see what carries into tomorrow.
    items = store.items_for_day(conn, today)
    summary = Classifier(config["classifier"]).summarize(today, items)
    store.set_summary(conn, today, summary)

    store.rollover(conn, today)
    conn.close()
    print(f"Nightly run complete for {today}.")


if __name__ == "__main__":
    main()
