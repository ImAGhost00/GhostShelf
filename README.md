# 👻 GhostShelf

**GhostShelf** is a self-hosted app for discovering and tracking books, comics, and manga — inspired by Shelf Mark for Calibre-Web Automated. It integrates with two powerful media servers:

| Content | Server |
|---------|--------|
| 📖 Books (epub, mobi, pdf…) | [Calibre-Web Automated](https://github.com/crocodilestick/Calibre-Web-Automated) |
| 🦸 Comics · 🎌 Manga | [Komga](https://komga.org) |

---

## Features

- **Multi-source book search** — Open Library & Google Books
- **Multi-source manga search** — MangaDex & AniList
- **Western comics search** — ComicVine (free API key required)
- **Watchlist** — track items as wanted → found → downloaded
- **Download queue** — log and manage download entries with direct links
- **Komga integration** — browse libraries, trigger scans
- **CWA integration** — connection check and ingest folder info
- **Dark ghost theme** — clean, responsive UI

---

## Quick Start (Docker)

```bash
# 1. Clone the repo
git clone https://github.com/your-user/ghostshelf
cd ghostshelf

# 2. Set up environment
cp .env.example .env
#    → optional: edit DEBUG/CORS/database values

# 3. Start GhostShelf
docker compose up -d

# UI  → http://localhost:4140
# API → http://localhost:8000/docs

# 4. Configure integrations in the app UI
#    Settings -> add CWA, Komga, qBittorrent, Prowlarr, and API keys
```

---

## Development (without Docker)

### Backend

```bash
cd backend

# Create & activate a virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/macOS

pip install -r requirements.txt

# Copy env (optional — defaults work for local dev)
cp ../.env.example .env

uvicorn app.main:app --reload --port 8000
```

Interactive API docs: <http://localhost:8000/docs>

### Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

The Vite dev server proxies `/api/*` to `http://localhost:8000`.

---

## Configuration

Integration settings are managed in the **Settings** page of the UI and persisted in the app database.

Environment variables in `.env` are optional fallback values and are no longer required in `docker-compose.yml`.

| Variable | Description |
|---|---|
| `CWA_URL` | Base URL of your Calibre-Web / CWA instance |
| `CWA_INGEST_FOLDER` | Path to the CWA ingest watch folder |
| `COMIC_INGEST_FOLDER` | Path for comic downloads |
| `MANGA_INGEST_FOLDER` | Path for manga downloads |
| `KOMGA_URL` | Base URL of your Komga instance |
| `KOMGA_USERNAME` | Komga login email |
| `KOMGA_PASSWORD` | Komga login password |
| `QBITTORRENT_URL` | Base URL of your qBittorrent Web UI |
| `QBITTORRENT_USERNAME` | qBittorrent username |
| `QBITTORRENT_PASSWORD` | qBittorrent password |
| `GOOGLE_BOOKS_API_KEY` | *(Optional)* Google Books key for higher quota |
| `COMICVINE_API_KEY` | ComicVine API key — needed for Western comics search |

---

## Search Sources

| Source | Type | Key needed? |
|--------|------|-------------|
| Open Library | Books | No |
| Google Books | Books | No (optional for quota) |
| MangaDex | Manga | No |
| AniList | Manga | No |
| ComicVine | Comics | Yes (free) |

---

## Project Structure

```
ghostshelf/
├── backend/              FastAPI backend
│   └── app/
│       ├── main.py       App entry point
│       ├── config.py     Settings (pydantic-settings)
│       ├── database.py   SQLAlchemy async engine
│       ├── models/       SQLAlchemy ORM models
│       ├── routers/      API route handlers
│       └── services/     Search & integration logic
├── frontend/             React + TypeScript (Vite)
│   └── src/
│       ├── pages/        Route pages
│       ├── components/   Shared UI components
│       ├── services/     API client
│       └── types/        TypeScript types
├── docker-compose.yml
└── .env.example
```

---

## API Reference

Interactive docs available at `/docs` (Swagger) and `/redoc`.

| Endpoint | Description |
|---|---|
| `GET /api/books/search?q=` | Search books |
| `GET /api/comics/search?q=` | Search comics/manga |
| `GET/POST /api/watchlist` | List / add watchlist items |
| `PATCH /api/watchlist/{id}` | Update status or notes |
| `DELETE /api/watchlist/{id}` | Remove item |
| `GET/POST /api/downloads` | List / queue downloads |
| `GET /api/integrations/komga/status` | Check Komga connection |
| `GET /api/integrations/komga/libraries` | List Komga libraries |
| `POST /api/integrations/komga/libraries/{id}/scan` | Trigger library scan |
| `GET /api/integrations/cwa/status` | Check CWA connection |
| `GET/POST /api/settings` | Get / update settings |

---

## License

MIT
