from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = BackgroundScheduler(daemon=True)


def run_delivery_cycle(app):
    with app.app_context():
        from feeds import fetch_all_feeds
        from searcher import search_all_categories
        from telegram_bot import deliver_news

        fetch_all_feeds()
        search_all_categories()
        deliver_news()


def rebuild_schedule(app):
    scheduler.remove_all_jobs()

    with app.app_context():
        from models import ScheduleSlot
        slots = ScheduleSlot.query.filter_by(active=True).all()

        for slot in slots:
            days = slot.days.split(",")
            day_map = {
                "0": "mon", "1": "tue", "2": "wed",
                "3": "thu", "4": "fri", "5": "sat", "6": "sun",
            }
            day_names = ",".join(day_map.get(d.strip(), "") for d in days if d.strip() in day_map)
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
    rebuild_schedule(app)
    if not scheduler.running:
        scheduler.start()
