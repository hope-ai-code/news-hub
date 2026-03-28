"""
Web search integration for news categories.

Uses DuckDuckGo to find recent news articles for categories configured
with source_type "web_search" or "both". Results are stored as Article
rows alongside RSS-sourced articles.
"""

from datetime import datetime, timezone
from models import db, Article, Category


def search_all_categories():
    """Run web searches for all active search-enabled categories.

    Returns the number of newly stored articles.
    """
    categories = Category.query.filter(
        Category.active == True,
        Category.source_type.in_(["web_search", "both"]),
    ).all()

    new_count = 0
    for cat in categories:
        if cat.search_query:
            new_count += _search_category(cat)

    db.session.commit()
    return new_count


def _search_category(category):
    """Search DuckDuckGo News for a single category's query.

    Fetches up to 10 results and inserts any that don't already exist
    in the database (deduplicated by URL).
    """
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

        if Article.query.filter_by(url=url).first():
            continue

        article = Article(
            feed_id=None,  # No feed for web search results
            category_id=category.id,
            title=title[:500],
            url=url[:500],
            summary=(r.get("body", "") or "")[:300],
            published_at=datetime.now(timezone.utc),
        )
        db.session.add(article)
        new_count += 1

    return new_count
