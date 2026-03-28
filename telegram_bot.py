"""
Telegram delivery module.

Formats collected articles into a categorized digest and sends them
via the Telegram Bot API. Messages are split into chunks to stay within
Telegram's 4096-character limit. Articles are rendered as clickable
HTML hyperlinks.
"""

import requests
from models import db, TelegramConfig, Article, Category, DeliveryLog
from datetime import datetime, timezone


def get_config():
    """Return the singleton TelegramConfig row."""
    return TelegramConfig.query.get(1)


def send_message(bot_token, chat_id, text, parse_mode="HTML"):
    """Send a single message via the Telegram Bot API.

    Returns (success: bool, response_text: str).
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    resp = requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    return resp.ok, resp.text


def send_test_message():
    """Send a test message to verify the current Telegram configuration."""
    config = get_config()
    if not config or not config.bot_token or not config.chat_id:
        return False, "Telegram not configured"

    ok, resp = send_message(
        config.bot_token, config.chat_id, "News Hub test message OK!"
    )
    return ok, resp


def build_digest(articles_by_category):
    """Build a list of Telegram-safe HTML message strings from grouped articles.

    Each category becomes a bold header followed by up to 10 linked article
    titles. Messages are split at ~4000 characters to stay within Telegram's
    4096-character limit.
    """
    messages = []
    current = ""

    for cat_name, articles in articles_by_category.items():
        section = f"\n<b>{_escape(cat_name)}</b>\n"
        for a in articles[:10]:
            line = f'- <a href="{a.url}">{_escape(a.title)}</a>\n'
            section += line

        # Start a new message if adding this section would exceed the limit
        if len(current) + len(section) > 4000:
            messages.append(current)
            current = section
        else:
            current += section

    if current.strip():
        messages.append(current)

    return messages


def _escape(text):
    """Escape HTML special characters for Telegram's HTML parse mode."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def deliver_news():
    """Send all undelivered articles to Telegram as a categorized digest.

    Returns (article_count: int, status_message: str).
    Articles are marked as delivered only if all messages send successfully.
    Each delivery attempt is logged to the DeliveryLog table.
    """
    config = get_config()
    if not config or not config.enabled or not config.bot_token or not config.chat_id:
        return 0, "Telegram not configured or disabled"

    # Fetch undelivered articles from active categories
    articles = (
        Article.query.filter_by(delivered=False)
        .join(Category)
        .filter(Category.active == True)
        .order_by(Category.name, Article.published_at.desc())
        .all()
    )

    if not articles:
        return 0, "No new articles"

    # Group articles by category name
    by_category = {}
    for a in articles:
        cat_name = a.category.name
        by_category.setdefault(cat_name, []).append(a)

    messages = build_digest(by_category)
    total = len(articles)
    errors = []

    for msg in messages:
        ok, resp = send_message(config.bot_token, config.chat_id, msg)
        if not ok:
            errors.append(resp)

    log = DeliveryLog(
        article_count=total,
        channel="telegram",
        status="success" if not errors else "error",
        error_message="; ".join(errors) if errors else None,
    )
    db.session.add(log)
    db.session.commit()

    return total, "OK" if not errors else "; ".join(errors)
