import feedparser
import re
from datetime import datetime, timezone
from time import mktime
from models import db, Feed, Article, Category


def strip_html(text):
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()[:300]


def fetch_all_feeds():
    categories = Category.query.filter(
        Category.active == True,
        Category.source_type.in_(["rss", "both"])
    ).all()

    new_count = 0
    for cat in categories:
        feeds = Feed.query.filter_by(category_id=cat.id, active=True).all()
        for feed in feeds:
            new_count += fetch_single_feed(feed)

    db.session.commit()
    return new_count


def fetch_single_feed(feed):
    try:
        parsed = feedparser.parse(feed.url)
    except Exception:
        return 0

    if parsed.bozo and not parsed.entries:
        return 0

    new_count = 0
    for entry in parsed.entries[:20]:
        url = entry.get("link", "").strip()
        title = entry.get("title", "").strip()
        if not url or not title:
            continue

        existing = Article.query.filter_by(url=url).first()
        if existing:
            continue

        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published = datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)
            except Exception:
                pass

        article = Article(
            feed_id=feed.id,
            category_id=feed.category_id,
            title=title[:500],
            url=url[:500],
            summary=strip_html(entry.get("summary", "")),
            published_at=published,
        )
        db.session.add(article)
        new_count += 1

    return new_count
