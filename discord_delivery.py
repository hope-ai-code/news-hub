"""
Discord delivery module.

Sends news digests to a Discord channel via webhook.
Discord webhooks accept markdown-formatted messages up to 2000 characters.
"""

import requests
from models import db, DiscordConfig, Article, Category, DeliveryLog


def get_config():
    return DiscordConfig.query.get(1)


def build_digest(articles_by_category):
    """Build a list of Discord markdown message strings from grouped articles."""
    messages = []
    current = ""

    for cat_name, articles in articles_by_category.items():
        section = f"\n**{cat_name}**\n"
        for a in articles[:10]:
            line = f"- [{a.title}]({a.url})\n"
            section += line

        if len(current) + len(section) > 1900:
            messages.append(current)
            current = section
        else:
            current += section

    if current.strip():
        messages.append(current)

    return messages


def send_test_message():
    """Send a test message to verify Discord webhook."""
    config = get_config()
    if not config or not config.webhook_url:
        return False, "Discord not configured"

    try:
        resp = requests.post(
            config.webhook_url,
            json={"content": "News Hub test message OK!"},
            timeout=30,
        )
        return resp.ok, resp.text
    except Exception as e:
        return False, str(e)


def deliver_news():
    """Send undelivered articles to Discord as markdown messages."""
    config = get_config()
    if not config or not config.enabled or not config.webhook_url:
        return 0, "Discord not configured or disabled"

    articles = (
        Article.query.filter_by(delivered=False)
        .join(Category)
        .filter(Category.active == True)
        .order_by(Category.name, Article.published_at.desc())
        .all()
    )

    if not articles:
        return 0, "No new articles"

    by_category = {}
    for a in articles:
        by_category.setdefault(a.category.name, []).append(a)

    messages = build_digest(by_category)
    total = len(articles)
    errors = []

    for msg in messages:
        try:
            resp = requests.post(
                config.webhook_url,
                json={"content": msg},
                timeout=30,
            )
            if not resp.ok:
                errors.append(resp.text)
        except Exception as e:
            errors.append(str(e))

    log = DeliveryLog(
        article_count=total,
        channel="discord",
        status="success" if not errors else "error",
        error_message="; ".join(errors) if errors else None,
    )
    db.session.add(log)
    db.session.commit()

    return total, "OK" if not errors else "; ".join(errors)
