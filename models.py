from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(100), nullable=False, unique=True)
    source_type = db.Column(db.String(20), nullable=False, default="rss")  # rss, web_search, both
    search_query = db.Column(db.String(200))
    active = db.Column(db.Boolean, default=True)
    feeds = db.relationship("Feed", backref="category", lazy=True)
    articles = db.relationship("Article", backref="category", lazy=True)


class Feed(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    active = db.Column(db.Boolean, default=True)


class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    feed_id = db.Column(db.Integer, db.ForeignKey("feed.id"), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    url = db.Column(db.String(500), nullable=False, unique=True)
    summary = db.Column(db.Text)
    published_at = db.Column(db.DateTime)
    fetched_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    delivered = db.Column(db.Boolean, default=False)


class TelegramConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bot_token = db.Column(db.String(200))
    chat_id = db.Column(db.String(100))
    enabled = db.Column(db.Boolean, default=False)


class ScheduleSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hour = db.Column(db.Integer, nullable=False)
    minute = db.Column(db.Integer, nullable=False, default=0)
    days = db.Column(db.String(50), nullable=False, default="0,1,2,3,4,5,6")  # CSV of day numbers
    active = db.Column(db.Boolean, default=True)


class DeliveryLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    delivered_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    article_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20))
    error_message = db.Column(db.Text)
