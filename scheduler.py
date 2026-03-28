"""
Background scheduler for automated news delivery.

Uses APScheduler to run delivery cycles at user-configured times.
Schedule is rebuilt from the database whenever delivery slots are
added, removed, or toggled through the web UI.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = BackgroundScheduler(daemon=True)

DAY_MAP = {
    "0": "mon", "1": "tue", "2": "wed",
    "3": "thu", "4": "fri", "5": "sat", "6": "sun",
}


def run_delivery_cycle(app):
    """Execute a full fetch-and-deliver cycle within the Flask app context.

    1. Fetch new articles from all active RSS feeds
    2. Run web searches for search-enabled categories
    3. Send undelivered articles to Telegram
    """
    with app.app_context():
        from feeds import fetch_all_feeds
        from searcher import search_all_categories
        from telegram_bot import deliver_news

        fetch_all_feeds()
        search_all_categories()
        deliver_news()


def rebuild_schedule(app):
    """Clear all scheduled jobs and recreate them from the database.

    Called on startup and whenever a ScheduleSlot is added, removed, or toggled.
    Uses an in-memory job store - the database is the source of truth.
    """
    scheduler.remove_all_jobs()

    with app.app_context():
        from models import ScheduleSlot

        slots = ScheduleSlot.query.filter_by(active=True).all()

        for slot in slots:
            day_names = ",".join(
                DAY_MAP[d.strip()]
                for d in slot.days.split(",")
                if d.strip() in DAY_MAP
            )
            if not day_names:
                continue

            trigger = CronTrigger(
                day_of_week=day_names,
                hour=slot.hour,
                minute=slot.minute,
                timezone="Europe/Oslo",
            )
            scheduler.add_job(
                run_delivery_cycle,
                trigger=trigger,
                args=[app],
                id=f"delivery_{slot.id}",
                replace_existing=True,
            )


def start_scheduler(app):
    """Initialize and start the background scheduler."""
    rebuild_schedule(app)
    if not scheduler.running:
        scheduler.start()
