from datetime import datetime, timezone
from models import db, Article, Category


def search_all_categories():
    categories = Category.query.filter(
        Category.active == True,
        Category.source_type.in_(["web_search", "both"])
    ).all()

    new_count = 0
    for cat in categories:
        if cat.search_query:
            new_count += search_category(cat)

    db.session.commit()
    return new_count


def search_category(category):
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.news(category.search_query, max_results=10))
    except Exception:
        return 0

    new_count = 0
    for r in results:
        url = r.get("url", "").strip()
        title = r.get("title", "").strip()
        if not url or not title:
            continue

        existing = Article.query.filter_by(url=url).first()
        if existing:
            continue

        article = Article(
            feed_id=None,
            category_id=category.id,
            title=title[:500],
            url=url[:500],
            summary=(r.get("body", "") or "")[:300],
            published_at=datetime.now(timezone.utc),
        )
        db.session.add(article)
        new_count += 1

    return new_count
