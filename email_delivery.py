"""
Email delivery module.

Sends news digests as HTML-formatted emails via SMTP.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from models import db, EmailConfig, Article, Category, DeliveryLog


def get_config():
    return EmailConfig.query.get(1)


def build_html_digest(articles_by_category):
    """Build an HTML email body from grouped articles."""
    html = '<html><body style="font-family: sans-serif; background: #1a1a2e; color: #e0e0e0; padding: 20px;">'
    html += '<h1 style="color: #00d4ff;">News Hub Digest</h1>'

    for cat_name, articles in articles_by_category.items():
        html += f'<h2 style="color: #7c83ff; border-bottom: 1px solid #333; padding-bottom: 5px;">{cat_name}</h2>'
        html += '<ul style="list-style: none; padding: 0;">'
        for a in articles[:10]:
            html += f'<li style="margin-bottom: 8px;"><a href="{a.url}" style="color: #00d4ff; text-decoration: none;">{a.title}</a>'
            if a.summary:
                html += f'<br><span style="color: #888; font-size: 0.9em;">{a.summary[:150]}</span>'
            html += '</li>'
        html += '</ul>'

    html += '</body></html>'
    return html


def send_test_message():
    """Send a test email to verify configuration."""
    config = get_config()
    if not config or not config.smtp_host or not config.to_address:
        return False, "Email not configured"

    msg = MIMEText("News Hub test message OK!", "plain")
    msg["Subject"] = "News Hub - Test Message"
    msg["From"] = config.from_address or config.smtp_user
    msg["To"] = config.to_address

    try:
        if config.use_tls:
            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30)
            server.starttls()
        else:
            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30)

        if config.smtp_user and config.smtp_password:
            server.login(config.smtp_user, config.smtp_password)
        server.send_message(msg)
        server.quit()
        return True, "OK"
    except Exception as e:
        return False, str(e)


def deliver_news():
    """Send undelivered articles as an HTML email digest."""
    config = get_config()
    if not config or not config.enabled or not config.smtp_host or not config.to_address:
        return 0, "Email not configured or disabled"

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

    html_body = build_html_digest(by_category)
    total = len(articles)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"News Hub Digest - {total} articles"
    msg["From"] = config.from_address or config.smtp_user
    msg["To"] = config.to_address
    msg.attach(MIMEText(html_body, "html"))

    try:
        if config.use_tls:
            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30)
            server.starttls()
        else:
            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30)

        if config.smtp_user and config.smtp_password:
            server.login(config.smtp_user, config.smtp_password)
        server.send_message(msg)
        server.quit()
        error = None
    except Exception as e:
        error = str(e)

    log = DeliveryLog(
        article_count=total,
        channel="email",
        status="success" if not error else "error",
        error_message=error,
    )
    db.session.add(log)
    db.session.commit()

    return total, "OK" if not error else error
