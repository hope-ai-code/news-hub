"""
Unified delivery dispatcher.

Delivers undelivered articles to all enabled channels. Articles are only
marked as delivered after at least one channel succeeds.
"""

from models import db, Article, Category


def deliver_all_channels():
    """Deliver news to all enabled channels.

    Calls each channel's deliver_news() independently. Articles are marked
    as delivered if at least one channel succeeds. Each channel logs its
    own DeliveryLog entry.

    Returns a dict of {channel_name: (count, message)}.
    """
    from telegram_bot import deliver_news as telegram_deliver
    from email_delivery import deliver_news as email_deliver
    from discord_delivery import deliver_news as discord_deliver
    from slack_delivery import deliver_news as slack_deliver
    from pushover_delivery import deliver_news as pushover_deliver
    from models import (
        TelegramConfig, EmailConfig, DiscordConfig,
        SlackConfig, PushoverConfig,
    )

    results = {}
    any_success = False

    # Collect which channels are enabled
    channels = []

    tg = TelegramConfig.query.get(1)
    if tg and tg.enabled and tg.bot_token and tg.chat_id:
        channels.append(("telegram", telegram_deliver))

    em = EmailConfig.query.get(1)
    if em and em.enabled:
        channels.append(("email", email_deliver))

    dc = DiscordConfig.query.get(1)
    if dc and dc.enabled and dc.webhook_url:
        channels.append(("discord", discord_deliver))

    sl = SlackConfig.query.get(1)
    if sl and sl.enabled and sl.webhook_url:
        channels.append(("slack", slack_deliver))

    po = PushoverConfig.query.get(1)
    if po and po.enabled and po.app_token and po.user_key:
        channels.append(("pushover", pushover_deliver))

    if not channels:
        return {"none": (0, "No delivery channels enabled")}

    for name, deliver_fn in channels:
        try:
            count, msg = deliver_fn()
            results[name] = (count, msg)
            if count > 0 and "error" not in msg.lower():
                any_success = True
        except Exception as e:
            results[name] = (0, str(e))

    # Mark articles as delivered if at least one channel succeeded
    if any_success:
        articles = (
            Article.query.filter_by(delivered=False)
            .join(Category)
            .filter(Category.active == True)
            .all()
        )
        for a in articles:
            a.delivered = True
        db.session.commit()

    return results
