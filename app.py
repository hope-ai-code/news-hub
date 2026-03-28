import json
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from models import db, Category, Feed, Article, TelegramConfig, ScheduleSlot, DeliveryLog
from scheduler import start_scheduler, rebuild_schedule

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:////app/data/news_hub.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)


def seed_defaults():
    if Category.query.first():
        return
    config_path = os.path.join(os.path.dirname(__file__), "config", "default_feeds.json")
    with open(config_path) as f:
        data = json.load(f)

    for cat_data in data["categories"]:
        cat = Category(
            name=cat_data["name"],
            slug=cat_data["slug"],
            source_type=cat_data["source_type"],
            search_query=cat_data.get("search_query"),
        )
        db.session.add(cat)
        db.session.flush()

        for feed_data in cat_data.get("feeds", []):
            feed = Feed(
                category_id=cat.id,
                name=feed_data["name"],
                url=feed_data["url"],
                is_default=True,
            )
            db.session.add(feed)

    if not TelegramConfig.query.get(1):
        db.session.add(TelegramConfig(id=1))

    db.session.commit()


# --- Routes ---

@app.route("/")
def index():
    active_categories = Category.query.filter_by(active=True).count()
    active_feeds = Feed.query.filter_by(active=True).count()
    tg = TelegramConfig.query.get(1)
    telegram_ok = tg and tg.enabled and tg.bot_token and tg.chat_id
    pending_articles = Article.query.filter_by(delivered=False).count()
    schedules = ScheduleSlot.query.filter_by(active=True).all()
    recent_logs = DeliveryLog.query.order_by(DeliveryLog.delivered_at.desc()).limit(5).all()
    recent_articles = (
        Article.query.order_by(Article.fetched_at.desc()).limit(20).all()
    )

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for s in schedules:
        s.days_display = ", ".join(day_names[int(d)] for d in s.days.split(",") if d.strip().isdigit())

    return render_template("index.html",
        active_categories=active_categories,
        active_feeds=active_feeds,
        telegram_ok=telegram_ok,
        pending_articles=pending_articles,
        schedules=schedules,
        recent_logs=recent_logs,
        recent_articles=recent_articles,
    )


@app.route("/categories")
def categories():
    cats = Category.query.order_by(Category.name).all()
    return render_template("categories.html", categories=cats)


@app.route("/categories/toggle/<int:cat_id>", methods=["POST"])
def toggle_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    cat.active = not cat.active
    db.session.commit()
    flash(f"{'Enabled' if cat.active else 'Disabled'} {cat.name}", "success")
    return redirect(url_for("categories"))


@app.route("/feeds")
def feeds():
    cats = Category.query.order_by(Category.name).all()
    return render_template("feeds.html", categories=cats)


@app.route("/feeds/add", methods=["POST"])
def add_feed():
    name = request.form.get("name", "").strip()
    url = request.form.get("url", "").strip()
    category_id = request.form.get("category_id", type=int)
    if name and url and category_id:
        feed = Feed(name=name, url=url, category_id=category_id, is_default=False)
        db.session.add(feed)
        db.session.commit()
        flash(f"Added feed: {name}", "success")
    else:
        flash("Missing fields", "danger")
    return redirect(url_for("feeds"))


@app.route("/feeds/toggle/<int:feed_id>", methods=["POST"])
def toggle_feed(feed_id):
    feed = Feed.query.get_or_404(feed_id)
    feed.active = not feed.active
    db.session.commit()
    return redirect(url_for("feeds"))


@app.route("/feeds/delete/<int:feed_id>", methods=["POST"])
def delete_feed(feed_id):
    feed = Feed.query.get_or_404(feed_id)
    if not feed.is_default:
        db.session.delete(feed)
        db.session.commit()
        flash("Feed removed", "success")
    return redirect(url_for("feeds"))


@app.route("/telegram", methods=["GET", "POST"])
def telegram():
    config = TelegramConfig.query.get(1)
    if not config:
        config = TelegramConfig(id=1)
        db.session.add(config)
        db.session.commit()

    if request.method == "POST":
        config.bot_token = request.form.get("bot_token", "").strip()
        config.chat_id = request.form.get("chat_id", "").strip()
        config.enabled = "enabled" in request.form
        db.session.commit()
        flash("Telegram settings saved", "success")
        return redirect(url_for("telegram"))

    return render_template("telegram.html", config=config)


@app.route("/telegram/test", methods=["POST"])
def telegram_test():
    from telegram_bot import send_test_message
    ok, msg = send_test_message()
    flash("Test message sent!" if ok else f"Failed: {msg}", "success" if ok else "danger")
    return redirect(url_for("telegram"))


@app.route("/schedule")
def schedule():
    slots = ScheduleSlot.query.order_by(ScheduleSlot.hour, ScheduleSlot.minute).all()
    return render_template("schedule.html", slots=slots)


@app.route("/schedule/add", methods=["POST"])
def add_schedule():
    time_str = request.form.get("time", "08:00")
    days = request.form.getlist("days")
    if not days:
        flash("Select at least one day", "danger")
        return redirect(url_for("schedule"))

    hour, minute = map(int, time_str.split(":"))
    slot = ScheduleSlot(hour=hour, minute=minute, days=",".join(days))
    db.session.add(slot)
    db.session.commit()
    rebuild_schedule(app)
    flash(f"Added delivery at {time_str}", "success")
    return redirect(url_for("schedule"))


@app.route("/schedule/toggle/<int:slot_id>", methods=["POST"])
def toggle_schedule(slot_id):
    slot = ScheduleSlot.query.get_or_404(slot_id)
    slot.active = not slot.active
    db.session.commit()
    rebuild_schedule(app)
    return redirect(url_for("schedule"))


@app.route("/schedule/delete/<int:slot_id>", methods=["POST"])
def delete_schedule(slot_id):
    slot = ScheduleSlot.query.get_or_404(slot_id)
    db.session.delete(slot)
    db.session.commit()
    rebuild_schedule(app)
    flash("Slot removed", "success")
    return redirect(url_for("schedule"))


@app.route("/fetch-now", methods=["POST"])
def fetch_now():
    from feeds import fetch_all_feeds
    from searcher import search_all_categories
    rss_count = fetch_all_feeds()
    search_count = search_all_categories()
    flash(f"Fetched {rss_count} RSS + {search_count} search articles", "success")
    return redirect(url_for("index"))


@app.route("/deliver-now", methods=["POST"])
def deliver_now():
    from telegram_bot import deliver_news
    count, msg = deliver_news()
    if count > 0:
        flash(f"Delivered {count} articles: {msg}", "success")
    else:
        flash(f"Nothing to deliver: {msg}", "danger")
    return redirect(url_for("index"))


if __name__ == "__main__":
    os.makedirs(os.path.join(os.path.dirname(__file__), "data"), exist_ok=True)
    with app.app_context():
        db.create_all()
        seed_defaults()
    start_scheduler(app)
    app.run(host="0.0.0.0", port=5000, debug=False)
