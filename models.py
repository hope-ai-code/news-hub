"""
Database models for News Hub.

Uses Flask-SQLAlchemy with SQLite. The schema covers news categories,
RSS feeds, fetched articles, Telegram delivery config, scheduling,
and delivery logs.
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()


class Category(db.Model):
    """A news category (e.g. Tech, World Politics, Science).

    Categories can pull articles from RSS feeds, web search, or both.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(100), nullable=False, unique=True)
    source_type = db.Column(db.String(20), nullable=False, default="rss")  # rss | web_search | both
    search_query = db.Column(db.String(200))  # Used when source_type includes web_search
    active = db.Column(db.Boolean, default=True)
    feeds = db.relationship("Feed", backref="category", lazy=True)
    articles = db.relationship("Article", backref="category", lazy=True)


class Feed(db.Model):
    """An RSS feed URL belonging to a category.

    Feeds marked is_default=True ship with the app and cannot be deleted
    through the UI (only toggled on/off). Custom feeds can be added and removed.
    """
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    active = db.Column(db.Boolean, default=True)


class Article(db.Model):
    """A single news article fetched from an RSS feed or web search.

    Articles are deduplicated by URL. The `delivered` flag tracks whether
    the article has been sent via Telegram.
    """
    id = db.Column(db.Integer, primary_key=True)
    feed_id = db.Column(db.Integer, db.ForeignKey("feed.id"), nullable=True)  # NULL for web search results
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    url = db.Column(db.String(500), nullable=False, unique=True)
    summary = db.Column(db.Text)
    published_at = db.Column(db.DateTime)
    fetched_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    delivered = db.Column(db.Boolean, default=False)


class TelegramConfig(db.Model):
    """Singleton row (id=1) holding the Telegram bot credentials.

    Store bot_token and chat_id here. Set enabled=True to activate
    scheduled delivery.
    """
    id = db.Column(db.Integer, primary_key=True)
    bot_token = db.Column(db.String(200))
    chat_id = db.Column(db.String(100))
    enabled = db.Column(db.Boolean, default=False)


class ScheduleSlot(db.Model):
    """A recurring delivery time slot.

    Each slot defines a time (hour:minute) and which days of the week
    it should fire. Days are stored as a comma-separated string of
    integers (0=Mon, 1=Tue, ..., 6=Sun).
    """
    id = db.Column(db.Integer, primary_key=True)
    hour = db.Column(db.Integer, nullable=False)
    minute = db.Column(db.Integer, nullable=False, default=0)
    days = db.Column(db.String(50), nullable=False, default="0,1,2,3,4,5,6")
    active = db.Column(db.Boolean, default=True)


class DeliveryLog(db.Model):
    """Record of each delivery attempt (success or failure)."""
    id = db.Column(db.Integer, primary_key=True)
    delivered_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    article_count = db.Column(db.Integer, default=0)
    channel = db.Column(db.String(50), default="telegram")  # telegram, email, discord, slack, pushover
    status = db.Column(db.String(20))  # "success" or "error"
    error_message = db.Column(db.Text)


class EmailConfig(db.Model):
    """Singleton row (id=1) holding SMTP email configuration."""
    id = db.Column(db.Integer, primary_key=True)
    smtp_host = db.Column(db.String(200))
    smtp_port = db.Column(db.Integer, default=587)
    smtp_user = db.Column(db.String(200))
    smtp_password = db.Column(db.String(200))
    use_tls = db.Column(db.Boolean, default=True)
    from_address = db.Column(db.String(200))
    to_address = db.Column(db.String(200))
    enabled = db.Column(db.Boolean, default=False)


class DiscordConfig(db.Model):
    """Singleton row (id=1) holding Discord webhook configuration."""
    id = db.Column(db.Integer, primary_key=True)
    webhook_url = db.Column(db.String(500))
    enabled = db.Column(db.Boolean, default=False)


class SlackConfig(db.Model):
    """Singleton row (id=1) holding Slack webhook configuration."""
    id = db.Column(db.Integer, primary_key=True)
    webhook_url = db.Column(db.String(500))
    enabled = db.Column(db.Boolean, default=False)


class PushoverConfig(db.Model):
    """Singleton row (id=1) holding Pushover configuration."""
    id = db.Column(db.Integer, primary_key=True)
    app_token = db.Column(db.String(200))
    user_key = db.Column(db.String(200))
    enabled = db.Column(db.Boolean, default=False)


class RSSOutputConfig(db.Model):
    """Singleton row (id=1) holding RSS output feed configuration."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), default="News Hub Digest")
    description = db.Column(db.String(500), default="Curated news digest from News Hub")
    enabled = db.Column(db.Boolean, default=False)
