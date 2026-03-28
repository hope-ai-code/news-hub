import requests
from models import db, TelegramConfig, Article, Category, DeliveryLog
from datetime import datetime, timezone


def get_config():
    return TelegramConfig.query.get(1)


def send_message(bot_token, chat_id, text, parse_mode="HTML"):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }, timeout=30)
    return resp.ok, resp.text


def send_test_message():
    config = get_config()
    if not config or not config.bot_token or not config.chat_id:
        return False, "Telegram not configured"

    ok, resp = send_message(config.bot_token, config.chat_id, "News Hub test message OK!")
    return ok, resp


def build_digest(articles_by_category):
    messages = []
    current = ""

    for cat_name, articles in articles_by_category.items():
        section = f"\n<b>{cat_name}</b>\n"
        for a in articles[:10]:
            title = a.title.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
            line = f'- <a href="{a.url}">{title}</a>\n'
            section += line

        if len(current) + len(section) > 4000:
            messages.append(current)
            current = section
        else:
            current += section

    if current.strip():
        messages.append(current)

    return messages


def deliver_news():
    config = get_config()
    if not config or not config.enabled or not config.bot_token or not config.chat_id:
        return 0, "Telegram not configured or disabled"

    articles = (
        Article.query
        .filter_by(delivered=False)
        .join(Category)
        .filter(Category.active == True)
        .order_by(Category.name, Article.published_at.desc())
        .all()
    )

    if not articles:
        return 0, "No new articles"

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

    if not errors:
        for a in articles:
            a.delivered = True
        db.session.commit()

    log = DeliveryLog(
        article_count=total,
        status="success" if not errors else "error",
        error_message="; ".join(errors) if errors else None,
    )
    db.session.add(log)
    db.session.commit()

    return total, "OK" if not errors else "; ".join(errors)
