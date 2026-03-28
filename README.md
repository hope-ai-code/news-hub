# News Hub

Self-hosted news aggregation with scheduled Telegram delivery.

News Hub collects articles from RSS feeds and web searches, organizes them into categories, and delivers digests to Telegram on a schedule you control. All news items link back to the original source.

![Python](https://img.shields.io/badge/python-3.11-blue)
![Flask](https://img.shields.io/badge/flask-3.1-green)
![Docker](https://img.shields.io/badge/docker-ready-blue)
![License](https://img.shields.io/badge/license-MIT-yellow)

## Features

- **8 default news categories** - Tech, World Politics, Norwegian News, EU News, Science, Business, Sports, Entertainment
- **RSS feed aggregation** - Ships with curated default feeds; add your own custom feeds via the web UI
- **Web search integration** - Uses DuckDuckGo to supplement RSS for broader news coverage
- **Telegram delivery** - Receive categorized news digests with clickable source links
- **Flexible scheduling** - Choose which days and times to receive your news
- **Manual controls** - Fetch and deliver on demand from the dashboard
- **Dark-themed web UI** - Clean Bootstrap 5 interface for managing everything
- **SQLite storage** - Zero-config database, persisted via Docker volume
- **Single container** - One Docker image, no external dependencies

## Quick Start

### Docker (recommended)

```bash
git clone https://github.com/youruser/news-hub.git
cd news-hub
docker compose up -d
```

The web UI will be available at **http://localhost:2003**.

### Without Docker

```bash
git clone https://github.com/youruser/news-hub.git
cd news-hub
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Runs on **http://localhost:5000** by default.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | Random (regenerated on restart) | Flask session secret. Set for persistent sessions. |
| `DATABASE_URL` | `sqlite:////app/data/news_hub.db` | SQLAlchemy database URI |
| `PORT` | `5000` | Port the app listens on inside the container |
| `TZ` | `UTC` | Timezone for scheduled deliveries (e.g. `Europe/Oslo`) |

Copy `.env.example` to `.env` and edit as needed:

```bash
cp .env.example .env
```

### Setting up Telegram

1. Message [@BotFather](https://t.me/BotFather) on Telegram to create a bot and get a **bot token**
2. Send a message to your new bot, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates` to find your **chat ID**
3. Enter both values on the **Telegram** page in the web UI
4. Click **Send Test Message** to verify
5. Enable the toggle and save

### Adding Custom RSS Feeds

Navigate to the **Feeds** page and use the form at the top to add any RSS/Atom feed URL. Assign it to an existing category. Custom feeds can be toggled on/off or deleted at any time.

### Scheduling Deliveries

On the **Schedule** page, add time slots specifying the hour and which days of the week. News Hub will automatically fetch fresh articles and deliver them to Telegram at each configured time.

## Architecture

```
news-hub/
├── app.py              # Flask app, routes, and startup
├── models.py           # SQLAlchemy database models
├── feeds.py            # RSS feed fetching with feedparser
├── searcher.py         # DuckDuckGo web search integration
├── telegram_bot.py     # Telegram message formatting and delivery
├── scheduler.py        # APScheduler background job management
├── config/
│   └── default_feeds.json  # Default categories and RSS feeds
├── templates/          # Jinja2 HTML templates
├── static/             # CSS styles
├── data/               # SQLite database (Docker volume)
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

### How Delivery Works

1. **Fetch** - RSS feeds are parsed and new articles stored in SQLite. Web searches run for categories that have them enabled.
2. **Deduplicate** - Articles are matched by URL to avoid sending the same story twice.
3. **Deliver** - Undelivered articles are grouped by category and sent as HTML-formatted Telegram messages with clickable links.
4. **Log** - Each delivery attempt is recorded with status and article count.

This cycle runs automatically at each scheduled time, or manually via the dashboard buttons.

## Default News Sources

| Category | Feeds |
|----------|-------|
| Tech | Hacker News, TechCrunch, The Verge, Ars Technica |
| World Politics | BBC World, Reuters, Al Jazeera |
| Norwegian News | NRK, VG + web search |
| EU News | Euronews, Politico Europe + web search |
| Science | Science Daily, Phys.org |
| Business | CNBC, BBC Business |
| Sports | BBC Sport, ESPN |
| Entertainment | Variety, The Hollywood Reporter |

All default feeds can be disabled. Add your own feeds to any category.

## Tech Stack

- **[Flask](https://flask.palletsprojects.com/)** - Web framework
- **[Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/)** - ORM / database
- **[feedparser](https://feedparser.readthedocs.io/)** - RSS/Atom feed parsing
- **[APScheduler](https://apscheduler.readthedocs.io/)** - Background job scheduling
- **[duckduckgo-search](https://github.com/deedy5/duckduckgo_search)** - Web search (no API key needed)
- **[Bootstrap 5](https://getbootstrap.com/)** - Frontend UI (CDN)

## License

[MIT](LICENSE)
