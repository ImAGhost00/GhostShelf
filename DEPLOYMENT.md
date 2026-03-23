# GhostWorld + GhostShelf Deployment Guide

## ⚙️ Setup Instructions

### 1. Prerequisites

- Docker and Docker Compose installed
- Media storage mounted (typically `/mnt/mediapool`)
- Config directory structure (`/opt/ghostworld/config/*`)
- VPN account (ProtonVPN for Gluetun)
- Wireguard private key for Gluetun

### 2. Directory Structure

Create these directories on your host:

```bash
mkdir -p /opt/ghostworld/config/{komga,wizarr,cwa,prowlarr,qbittorrent,jellyfin,sonarr,radarr,lidarr,bazarr,seerr,recyclarr,shelfmark}
mkdir -p /opt/ghostworld/{tdarr,jellystat,homarr}
mkdir -p /mnt/mediapool/{comics,manga,books,book-ingest,downloads}

# Set permissions
sudo chown -R 1000:1000 /opt/ghostworld /mnt/mediapool
```

### 3. Customize `docker-compose.local.yml`

Update these values:

| Variable | Current | Update To |
|----------|---------|-----------|
| `WIREGUARD_PRIVATE_KEY` | `your-wireguard-private-key-here` | Your actual ProtonVPN WireGuard key |
| `POSTGRES_PASSWORD` | `your-postgres-password-here` | Strong random password |
| `JWT_SECRET` | `your-jwt-secret-change-this` | Strong random 32-char string |
| `SECRET_ENCRYPTION_KEY` | `your-secret-encryption-key-change-this` | Strong random 64-char hex string |
| `UN_SONARR_0_API_KEY` | `your-sonarr-api-key` | Sonarr API key |
| `UN_RADARR_0_API_KEY` | `your-radarr-api-key` | Radarr API key |
| Media paths | `/mnt/mediapool` | Your actual media mount point |
| Config paths | `/opt/ghostworld/config` | Your actual config directory |
| TZ | `America/New_York` | Your timezone |

### 4. Start the Stack

```bash
# From the ghostshelf directory
docker compose -f docker-compose.local.yml up -d

# Monitor startup
docker compose -f docker-compose.local.yml logs -f
```

### 5. Initialize GhostShelf

After backend is running, create the default admin user:

```bash
docker exec ghostshelf-backend python -m app.init_admin
```

Output:
```
✓ Created default admin user
  Username: admin
  Token: <uuid-token>
  Email: admin@ghostshelf.local
```

### 6. Access Services

| Service | URL | Notes |
|---------|-----|-------|
| **GhostShelf** | `http://localhost:4141` | Main UI — login with admin token |
| **Wizarr** | `http://localhost:5690` | User management & auth |
| **Komga** | `http://localhost:25600` | Comics/Manga library |
| **CWA** | `http://localhost:8083` | Books library |
| **Jellyfin** | `http://localhost:8096` | Media server |
| **Prowlarr** | `http://localhost:9696` | Indexer manager |
| **Sonarr** | `http://localhost:8989` | TV indexer |
| **Radarr** | `http://localhost:7878` | Movie indexer |
| **Lidarr** | `http://localhost:8686` | Music indexer |
| **Bazarr** | `http://localhost:6767` | Subtitles |
| **Seerr** | `http://localhost:5055` | Request management |
| **QBittorrent** | `http://localhost:8081` | Torrent client (via Gluetun) |
| **Tdarr** | `http://localhost:8265` | Transcoding |
| **Jellystat** | `http://localhost:3000` | Jellyfin stats |
| **DashDot** | `http://localhost:3001` | System monitoring |
| **Homarr** | `http://localhost:7575` | Dashboard |

### 7. GhostShelf Login

1. Open `http://localhost:4141`
2. Use token from init_admin output
3. This creates a JWT session valid for 7 days
4. Configure integrations in Settings page

### 8. Common Tasks

**Stop all services:**
```bash
docker compose -f docker-compose.local.yml down
```

**View logs:**
```bash
docker compose -f docker-compose.local.yml logs -f <service-name>
docker compose -f docker-compose.local.yml logs -f ghostshelf-backend
```

**Rebuild GhostShelf after code changes:**
```bash
docker compose -f docker-compose.local.yml up -d --build ghostshelf-backend ghostshelf-frontend
```

**Access backend shell:**
```bash
docker exec -it ghostshelf-backend /bin/bash
```

**Reinitialize admin user:**
```bash
docker exec ghostshelf-backend python -m app.init_admin
```

---

## 🔐 Security Notes

⚠️ **DO NOT commit `docker-compose.local.yml` to git** — it contains sensitive values.

Before production deployment:
- Generate strong random values for all `_SECRET_`, `_PASSWORD_`, `_KEY` variables
- Use a reverse proxy (Traefik, Nginx) with SSL
- Restrict network access to services
- Use `.env.local` file with proper permissions instead of embedding secrets
- Implement regular backups

---

## 📦 Services Overview

### Core
- **GhostShelf**: Discovery & tracking for books/comics/manga
- **Wizarr**: Centralized user management & authentication
- **Jellyfin**: Media server (TV, movies, music)

### Books
- **Calibre-Web-Automated (CWA)**: E-book library management
- **Shelfmark**: E-book downloader

### Comics
- **Komga**: Comics/manga library

### Downloads
- **Prowlarr**: Indexer aggregator
- **Sonarr**: TV show automation
- **Radarr**: Movie automation
- **Lidarr**: Music automation
- **Bazarr**: Subtitle automation
- **QBittorrent**: Torrent client (via Gluetun VPN)
- **Unpackerr**: Archive extraction & post-processing
- **Recyclarr**: Quality profile sync

### Tools
- **Tdarr**: Transcoding queue
- **Seerr**: User request management
- **Jellystat**: Jellyfin statistics
- **DashDot**: System monitoring
- **Homarr**: Dashboard/launcher
- **Watchtower**: Automatic container updates

---

## 🐛 Troubleshooting

**GhostShelf won't start:**
- Check Wizarr is running: `docker logs wizarr`
- Verify database path exists: `ls /opt/ghostworld/config/wizarr/`
- Check logs: `docker logs ghostshelf-backend`

**Can't log in:**
- Ensure admin user exists: `docker exec ghostshelf-backend python -m app.init_admin`
- Check JWT secret is set: `docker exec ghostshelf-backend env | grep SECRET_KEY`

**Services can't communicate:**
- Verify network: `docker network inspect ghostworld_ghost_network`
- Check DNS: `docker exec ghostshelf-backend nslookup wizarr`

**VPN issues (Gluetun):**
- Verify WireGuard key: `docker logs gluetun | grep -i wireguard`
- Check VPN connection: `docker exec gluetun wget -qO- https://api.ipify.org`
