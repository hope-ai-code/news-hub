"""
RSS output module.

Generates an RSS 2.0 XML feed of collected articles so external readers
can subscribe to the News Hub digest.
"""

from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, tostring
from models import RSSOutputConfig, Article, Category


def get_config():
    return RSSOutputConfig.query.get(1)


def generate_feed(base_url="", limit=50):
    """Generate an RSS 2.0 XML string of recent articles.

    Args:
        base_url: The public URL of this News Hub instance (for feed links).
        limit: Maximum number of articles to include.

    Returns:
        XML string of the RSS feed, or None if RSS output is disabled.
    """
    config = get_config()
    if not config or not config.enabled:
        return None

    rss = Element("rss", version="2.0")
    channel = SubElement(rss, "channel")

    SubElement(channel, "title").text = config.title or "News Hub Digest"
    SubElement(channel, "description").text = config.description or "Curated news digest"
    SubElement(channel, "link").text = base_url or "http://localhost:2003"
    SubElement(channel, "lastBuildDate").text = datetime.now(timezone.utc).strftime(
        "%a, %d %b %Y %H:%M:%S +0000"
    )

    articles = (
        Article.query
        .join(Category)
        .filter(Category.active == True)
        .order_by(Article.fetched_at.desc())
        .limit(limit)
        .all()
    )

    for a in articles:
        item = SubElement(channel, "item")
        SubElement(item, "title").text = a.title
        SubElement(item, "link").text = a.url
        SubElement(item, "guid").text = a.url
        if a.summary:
            SubElement(item, "description").text = a.summary
        SubElement(item, "category").text = a.category.name
        if a.published_at:
            SubElement(item, "pubDate").text = a.published_at.strftime(
                "%a, %d %b %Y %H:%M:%S +0000"
            )

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(rss, encoding="unicode")
