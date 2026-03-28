"""
News Hub - Self-hosted news aggregation with Telegram delivery.

A lightweight web app that collects news from RSS feeds and web searches,
lets you organize them by category, and delivers digests to Telegram on
a configurable schedule.
"""

import json
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from models import (
    db, Category, Feed, Article, TelegramConfig, ScheduleSlot, DeliveryLog,
    EmailConfig, DiscordConfig, SlackConfig, PushoverConfig, RSSOutputConfig,
)
from scheduler import start_scheduler, rebuild_schedule

app = Flask(__name__)

# Use a persistent secret key so sessions survive restarts.
# Falls back to a random key if SECRET_KEY is not set (sessions reset on restart).
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))

# Database path is configurable; defaults to a SQLite file in ./data/
db_path = os.environ.get("DATABASE_URL", "sqlite:////app/data/news_hub.db")
app.config["SQLALCHEMY_DATABASE_URI"] = db_path
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)


def seed_defaults():
    """Populate the database with default categories and feeds on first run.

    Reads from config/default_feeds.json and creates Category + Feed rows.
    Also ensures a singleton TelegramConfig row exists.
    Skips entirely if any categories already exist (i.e., not a fresh database).
    """
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
        db.session.flush()  # Get the auto-generated cat.id for feed FK

        for feed_data in cat_data.get("feeds", []):
            feed = Feed(
                category_id=cat.id,
                name=feed_data["name"],
                url=feed_data["url"],
                is_default=True,
            )
            db.session.add(feed)

    # Singleton config rows for delivery channels
    if not TelegramConfig.query.get(1):
        db.session.add(TelegramConfig(id=1))
    if not EmailConfig.query.get(1):
        db.session.add(EmailConfig(id=1))
    if not DiscordConfig.query.get(1):
        db.session.add(DiscordConfig(id=1))
    if not SlackConfig.query.get(1):
        db.session.add(SlackConfig(id=1))
    if not PushoverConfig.query.get(1):
        db.session.add(PushoverConfig(id=1))
    if not RSSOutputConfig.query.get(1):
        db.session.add(RSSOutputConfig(id=1))

    db.session.commit()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Dashboard showing system status, recent articles, and delivery logs."""
    active_categories = Category.query.filter_by(active=True).count()
    active_feeds = Feed.query.filter_by(active=True).count()
    pending_articles = Article.query.filter_by(delivered=False).count()
    schedules = ScheduleSlot.query.filter_by(active=True).all()
    recent_logs = DeliveryLog.query.order_by(DeliveryLog.delivered_at.desc()).limit(10).all()
    recent_articles = Article.query.order_by(Article.fetched_at.desc()).limit(20).all()

    # Channel status
    tg = TelegramConfig.query.get(1)
    em = EmailConfig.query.get(1)
    dc = DiscordConfig.query.get(1)
    sl = SlackConfig.query.get(1)
    po = PushoverConfig.query.get(1)
    rss_cfg = RSSOutputConfig.query.get(1)

    channels = {
        "Telegram": tg and tg.enabled and tg.bot_token and tg.chat_id,
        "Email": em and em.enabled and em.smtp_host,
        "Discord": dc and dc.enabled and dc.webhook_url,
        "Slack": sl and sl.enabled and sl.webhook_url,
        "Pushover": po and po.enabled and po.app_token,
        "RSS Feed": rss_cfg and rss_cfg.enabled,
    }
    enabled_channels = [name for name, ok in channels.items() if ok]

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for s in schedules:
        s.days_display = ", ".join(
            day_names[int(d)] for d in s.days.split(",") if d.strip().isdigit()
        )

    return render_template(
        "index.html",
        active_categories=active_categories,
        active_feeds=active_feeds,
        enabled_channels=enabled_channels,
        pending_articles=pending_articles,
        schedules=schedules,
        recent_logs=recent_logs,
        recent_articles=recent_articles,
    )


@app.route("/categories")
def categories():
    """List all news categories with toggle controls."""
    cats = Category.query.order_by(Category.name).all()
    return render_template("categories.html", categories=cats)


@app.route("/categories/toggle/<int:cat_id>", methods=["POST"])
def toggle_category(cat_id):
    """Enable or disable a news category."""
    cat = Category.query.get_or_404(cat_id)
    cat.active = not cat.active
    db.session.commit()
    flash(f"{'Enabled' if cat.active else 'Disabled'} {cat.name}", "success")
    return redirect(url_for("categories"))


@app.route("/feeds")
def feeds():
    """List all RSS feeds grouped by category, with add/toggle/delete controls."""
    cats = Category.query.order_by(Category.name).all()
    return render_template("feeds.html", categories=cats)


@app.route("/feeds/add", methods=["POST"])
def add_feed():
    """Add a custom RSS feed URL to a category."""
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
    """Enable or disable a single RSS feed."""
    feed = Feed.query.get_or_404(feed_id)
    feed.active = not feed.active
    db.session.commit()
    return redirect(url_for("feeds"))


@app.route("/feeds/delete/<int:feed_id>", methods=["POST"])
def delete_feed(feed_id):
    """Remove a custom (non-default) RSS feed."""
    feed = Feed.query.get_or_404(feed_id)
    if not feed.is_default:
        db.session.delete(feed)
        db.session.commit()
        flash("Feed removed", "success")
    return redirect(url_for("feeds"))


@app.route("/telegram", methods=["GET", "POST"])
def telegram():
    """Configure Telegram bot token and chat ID for news delivery."""
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
    """Send a test message to verify Telegram configuration."""
    from telegram_bot import send_test_message

    ok, msg = send_test_message()
    flash(
        "Test message sent!" if ok else f"Failed: {msg}",
        "success" if ok else "danger",
    )
    return redirect(url_for("telegram"))


@app.route("/email", methods=["GET", "POST"])
def email():
    """Configure SMTP email delivery."""
    config = EmailConfig.query.get(1)
    if not config:
        config = EmailConfig(id=1)
        db.session.add(config)
        db.session.commit()

    if request.method == "POST":
        config.smtp_host = request.form.get("smtp_host", "").strip()
        config.smtp_port = int(request.form.get("smtp_port", 587))
        config.smtp_user = request.form.get("smtp_user", "").strip()
        config.smtp_password = request.form.get("smtp_password", "").strip()
        config.use_tls = "use_tls" in request.form
        config.from_address = request.form.get("from_address", "").strip()
        config.to_address = request.form.get("to_address", "").strip()
        config.enabled = "enabled" in request.form
        db.session.commit()
        flash("Email settings saved", "success")
        return redirect(url_for("email"))

    return render_template("email.html", config=config)


@app.route("/email/test", methods=["POST"])
def email_test():
    """Send a test email."""
    from email_delivery import send_test_message
    ok, msg = send_test_message()
    flash("Test email sent!" if ok else f"Failed: {msg}", "success" if ok else "danger")
    return redirect(url_for("email"))


@app.route("/discord", methods=["GET", "POST"])
def discord():
    """Configure Discord webhook delivery."""
    config = DiscordConfig.query.get(1)
    if not config:
        config = DiscordConfig(id=1)
        db.session.add(config)
        db.session.commit()

    if request.method == "POST":
        config.webhook_url = request.form.get("webhook_url", "").strip()
        config.enabled = "enabled" in request.form
        db.session.commit()
        flash("Discord settings saved", "success")
        return redirect(url_for("discord"))

    return render_template("discord.html", config=config)


@app.route("/discord/test", methods=["POST"])
def discord_test():
    """Send a test Discord message."""
    from discord_delivery import send_test_message
    ok, msg = send_test_message()
    flash("Test message sent!" if ok else f"Failed: {msg}", "success" if ok else "danger")
    return redirect(url_for("discord"))


@app.route("/slack", methods=["GET", "POST"])
def slack():
    """Configure Slack webhook delivery."""
    config = SlackConfig.query.get(1)
    if not config:
        config = SlackConfig(id=1)
        db.session.add(config)
        db.session.commit()

    if request.method == "POST":
        config.webhook_url = request.form.get("webhook_url", "").strip()
        config.enabled = "enabled" in request.form
        db.session.commit()
        flash("Slack settings saved", "success")
        return redirect(url_for("slack"))

    return render_template("slack.html", config=config)


@app.route("/slack/test", methods=["POST"])
def slack_test():
    """Send a test Slack message."""
    from slack_delivery import send_test_message
    ok, msg = send_test_message()
    flash("Test message sent!" if ok else f"Failed: {msg}", "success" if ok else "danger")
    return redirect(url_for("slack"))


@app.route("/pushover", methods=["GET", "POST"])
def pushover():
    """Configure Pushover push notification delivery."""
    config = PushoverConfig.query.get(1)
    if not config:
        config = PushoverConfig(id=1)
        db.session.add(config)
        db.session.commit()

    if request.method == "POST":
        config.app_token = request.form.get("app_token", "").strip()
        config.user_key = request.form.get("user_key", "").strip()
        config.enabled = "enabled" in request.form
        db.session.commit()
        flash("Pushover settings saved", "success")
        return redirect(url_for("pushover"))

    return render_template("pushover.html", config=config)


@app.route("/pushover/test", methods=["POST"])
def pushover_test():
    """Send a test Pushover notification."""
    from pushover_delivery import send_test_message
    ok, msg = send_test_message()
    flash("Test sent!" if ok else f"Failed: {msg}", "success" if ok else "danger")
    return redirect(url_for("pushover"))


@app.route("/rss-config", methods=["GET", "POST"])
def rss_config():
    """Configure RSS output feed."""
    config = RSSOutputConfig.query.get(1)
    if not config:
        config = RSSOutputConfig(id=1)
        db.session.add(config)
        db.session.commit()

    if request.method == "POST":
        config.title = request.form.get("title", "").strip() or "News Hub Digest"
        config.description = request.form.get("description", "").strip()
        config.enabled = "enabled" in request.form
        db.session.commit()
        flash("RSS output settings saved", "success")
        return redirect(url_for("rss_config"))

    return render_template("rss_config.html", config=config)


@app.route("/feed.xml")
def rss_feed():
    """Serve the RSS output feed."""
    from rss_output import generate_feed
    xml = generate_feed(base_url=request.host_url.rstrip("/"))
    if xml is None:
        return "RSS output is disabled", 404
    return xml, 200, {"Content-Type": "application/rss+xml; charset=utf-8"}


@app.route("/schedule")
def schedule():
    """View and manage scheduled delivery time slots."""
    slots = ScheduleSlot.query.order_by(ScheduleSlot.hour, ScheduleSlot.minute).all()
    return render_template("schedule.html", slots=slots)


@app.route("/schedule/add", methods=["POST"])
def add_schedule():
    """Add a new delivery time slot (day + time combination)."""
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
    """Enable or disable a delivery time slot."""
    slot = ScheduleSlot.query.get_or_404(slot_id)
    slot.active = not slot.active
    db.session.commit()
    rebuild_schedule(app)
    return redirect(url_for("schedule"))


@app.route("/schedule/delete/<int:slot_id>", methods=["POST"])
def delete_schedule(slot_id):
    """Remove a delivery time slot."""
    slot = ScheduleSlot.query.get_or_404(slot_id)
    db.session.delete(slot)
    db.session.commit()
    rebuild_schedule(app)
    flash("Slot removed", "success")
    return redirect(url_for("schedule"))


@app.route("/fetch-now", methods=["POST"])
def fetch_now():
    """Manually trigger fetching of all RSS feeds and web searches."""
    from feeds import fetch_all_feeds
    from searcher import search_all_categories

    rss_count = fetch_all_feeds()
    search_count = search_all_categories()
    flash(f"Fetched {rss_count} RSS + {search_count} search articles", "success")
    return redirect(url_for("index"))


@app.route("/deliver-now", methods=["POST"])
def deliver_now():
    """Manually trigger delivery of unread articles to all enabled channels."""
    from delivery import deliver_all_channels

    results = deliver_all_channels()
    total = sum(count for count, _ in results.values())
    if total > 0:
        parts = [f"{ch}: {count}" for ch, (count, msg) in results.items() if count > 0]
        flash(f"Delivered to {', '.join(parts)}", "success")
    else:
        flash("Nothing to deliver", "danger")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def upgrade_db():
    """Add new columns and tables to an existing database.

    SQLAlchemy's create_all() only creates missing tables. This function
    handles schema changes for existing tables (e.g. adding columns).
    """
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)

    # Add 'channel' column to delivery_log if missing
    if "delivery_log" in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns("delivery_log")]
        if "channel" not in columns:
            db.session.execute(
                text("ALTER TABLE delivery_log ADD COLUMN channel VARCHAR(50) DEFAULT 'telegram'")
            )
            db.session.commit()


if __name__ == "__main__":
    os.makedirs(os.path.join(os.path.dirname(__file__), "data"), exist_ok=True)
    with app.app_context():
        db.create_all()
        upgrade_db()
        seed_defaults()
    start_scheduler(app)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
