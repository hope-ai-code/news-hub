"""
Pushover delivery module.

Sends news digests as push notifications via the Pushover API.
Pushover messages have a 1024-character limit for the message body,
so digests are split into multiple notifications.
"""

import requests
from models import db, PushoverConfig, Article, Category, DeliveryLog

PUSHOVER_API = "https://api.pushover.net/1/messages.json"


def get_config():
    return PushoverConfig.query.get(1)


def build_digest(articles_by_category):
    """Build a list of HTML message strings for Pushover (1024 char limit)."""
    messages = []
    current = ""

    for cat_name, articles in articles_by_category.items():
        section = f"\n<b>{cat_name}</b>\n"
        for a in articles[:10]:
            line = f'- <a href="{a.url}">{a.title}</a>\n'
            section += line

        if len(current) + len(section) > 900:
            messages.append(current)
            current = section
        else:
            current += section

    if current.strip():
        messages.append(current)

    return messages


def send_test_message():
    """Send a test notification to verify Pushover configuration."""
    config = get_config()
    if not config or not config.app_token or not config.user_key:
        return False, "Pushover not configured"

    try:
        resp = requests.post(
            PUSHOVER_API,
            data={
                "token": config.app_token,
                "user": config.user_key,
                "message": "News Hub test message OK!",
                "title": "News Hub",
            },
            timeout=30,
        )
        return resp.ok, resp.text
    except Exception as e:
        return False, str(e)


def deliver_news():
    """Send undelivered articles as Pushover notifications."""
    config = get_config()
    if not config or not config.enabled or not config.app_token or not config.user_key:
        return 0, "Pushover not configured or disabled"

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

    for i, msg in enumerate(messages):
        try:
            resp = requests.post(
                PUSHOVER_API,
                data={
                    "token": config.app_token,
                    "user": config.user_key,
                    "message": msg,
                    "title": f"News Hub Digest ({i+1}/{len(messages)})",
                    "html": 1,
                },
                timeout=30,
            )
            if not resp.ok:
                errors.append(resp.text)
        except Exception as e:
            errors.append(str(e))

    log = DeliveryLog(
        article_count=total,
        channel="pushover",
        status="success" if not errors else "error",
        error_message="; ".join(errors) if errors else None,
    )
    db.session.add(log)
    db.session.commit()

    return total, "OK" if not errors else "; ".join(errors)
