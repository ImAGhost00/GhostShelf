# GhostShelf Security & Functionality Audit Report

**Date:** March 22, 2026  
**Application:** GhostShelf v1.0.0  
**Status:** Comprehensive audit covering security posture and functional integrity

---

## EXECUTIVE SUMMARY

GhostShelf is a FastAPI-based media discovery application that integrates with multiple external services (Komga, Calibre-Web, Prowlarr, qBittorrent). The application demonstrates a **modern authentication architecture** with JWT tokens and Wizarr integration, but has **several critical and medium-severity security concerns** that should be addressed before production deployment.

**Critical Issues:** 2  
**Medium Issues:** 8  
**Low Issues:** 5  
**Recommendations:** 12

---

## 🔴 CRITICAL SECURITY ISSUES

### 1. **CRITICAL: Hardcoded Default SECRET_KEY**
**Location:** [backend/app/routers/auth.py](backend/app/routers/auth.py#L20)

```python
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
```

**Issue:** The default SECRET_KEY is a placeholder string. If `SECRET_KEY` environment variable is not set, all JWT tokens will be signed with this weak, publicly-known key. This allows anyone to forge valid authentication tokens.

**Risk:** Complete authentication bypass, unauthorized access to all protected endpoints.

**Severity:** CRITICAL

**Remediation:**
- Generate a strong random SECRET_KEY (at least 32 bytes of random data)
- Store in environment variables or secrets management system
- **REMOVE the default fallback or fail loudly at startup if not set**
- Rotate this key and invalidate all existing tokens if deployed

**Recommended Fix:**
```python
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable must be set before startup")
```

---

### 2. **CRITICAL: Path Traversal Vulnerability in File Download Operations**
**Location:** [backend/app/services/download_service.py](backend/app/services/download_service.py#L20-L35)

**Issue:** While the code has `_safe_filename()` that removes path separators, it does NOT validate the destination folder path itself. An attacker can potentially:

1. Use the `destination` parameter in download requests to specify arbitrary file paths
2. Combined with symlink attacks, write files to sensitive locations
3. Overwrite existing files in system directories

```python
async def start_direct_download(
    # ...
    destination: str | None = None,  # ← User-controlled destination path
) -> dict[str, Any]:
    # ...
    folder = await _target_folder(db, content_type, destination)  # ← Can be attacker-supplied
    os.makedirs(folder, exist_ok=True)  # ← Creates any path
    filepath = os.path.join(folder, filename)  # ← Potential traversal
```

**Attack Vector:**
```
POST /api/downloads/direct
{
  "title": "test.pdf",
  "content_type": "book",
  "download_url": "https://example.com/test.pdf",
  "destination": "../../../../../../etc"  # Potential path traversal
}
```

**Risk:** Arbitrary file write, denial of service, potential system compromise.

**Severity:** CRITICAL

**Remediation:**
- **Validate destination paths** - ensure they're within allowed directories
- Use `os.path.realpath()` to resolve symlinks and validate the resolved path
- Implement a whitelist of allowed download directories
- Never trust user-supplied destination parameter directly

**Recommended Fix:**
```python
import os
from pathlib import Path

ALLOWED_DOWNLOAD_ROOTS = {
    "/media/MediaPool/books",
    "/media/MediaPool/comics",
    "/media/MediaPool/manga",
}

def _validate_destination(dest_path: str) -> bool:
    """Ensure destination is within allowed directories."""
    real_path = os.path.realpath(dest_path)
    for allowed_root in ALLOWED_DOWNLOAD_ROOTS:
        allowed_real = os.path.realpath(allowed_root)
        if real_path.startswith(allowed_real + os.sep) or real_path == allowed_real:
            return True
    return False

# In start_direct_download():
if explicit_destination and not _validate_destination(explicit_destination):
    raise ValueError("Destination outside allowed directories")
```

---

## 🟠 MEDIUM SECURITY CONCERNS

### 3. **MEDIUM: Insufficient Input Validation on Search Queries**
**Location:** [backend/app/routers/books.py](backend/app/routers/books.py#L13), [backend/app/routers/comics.py](backend/app/routers/comics.py#L13)

**Issue:** Search queries have only basic length validation (`min_length=1`), but no protection against:
- **ReDoS (Regular Expression Denial of Service)** attacks in book_search and comic_search services
- **Query injection** in external API calls
- **Resource exhaustion** via extremely long queries

```python
@router.get("/search")
async def search(
    q: str = Query(..., min_length=1, description="Search query"),  # ← Only checks min length
    # ...
):
```

**Risk:** DoS attacks, external API abuse, potential injection in downstream services.

**Severity:** MEDIUM

**Remediation:**
```python
@router.get("/search")
async def search(
    q: str = Query(
        ..., 
        min_length=1, 
        max_length=200,  # ← Add maximum length
        regex=r"^[a-zA-Z0-9\s\-&':().,]+$"  # ← Whitelist safe characters
    ),
    # ...
):
```

---

### 4. **MEDIUM: JWT Token Expiration Not Validated on Every Request**
**Location:** [backend/app/routers/auth.py](backend/app/routers/auth.py#L48-L53)

**Issue:** The JWT `exp` claim is set but `jwt.decode()` is called with proper algorithm validation. However, there's no explicit handling of token refresh or clear documentation about the 1-week expiration.

```python
def decode_access_token(token: str) -> dict | None:
    """Decode and validate JWT access token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.InvalidTokenError:
        return None
```

**Issue:** While `jwt.decode()` automatically validates expiration, the function silently swallows all JWT errors and returns `None`, making it hard to distinguish between expired tokens and invalid signatures.

**Risk:** Difficult debugging, potential for token reuse if client doesn't handle expiration properly.

**Severity:** MEDIUM

**Remediation:**
```python
def decode_access_token(token: str) -> dict | None:
    """Decode and validate JWT access token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return None
```

---

### 5. **MEDIUM: SQL Injection Risk in Wizarr User Lookup**
**Location:** [backend/app/wizarr_models.py](backend/app/wizarr_models.py#L48-L60)

**Issue:** While SQLAlchemy ORM is used (which provides parameterized queries), the code directly reads from Wizarr database using synchronous SQLite without any input sanitization. If Wizarr DB is compromised or misconfigured, GhostShelf could be affected.

More critically: The function doesn't handle exceptions properly and returns `None` on any database error, making attacks difficult to detect.

```python
def get_wizarr_user_by_token(token: str) -> WizarrUser | None:
    try:
        with Session(wizarr_engine) as session:
            user = session.query(WizarrUser).filter_by(token=token).first()
            # ...
            return user
    except Exception:  # ← Silently swallows all errors
        return None
```

**Risk:** Silent failures masking attacks, no audit trail of failed authentication attempts.

**Severity:** MEDIUM

**Remediation:**
```python
import logging
logger = logging.getLogger(__name__)

def get_wizarr_user_by_token(token: str) -> WizarrUser | None:
    try:
        with Session(wizarr_engine) as session:
            user = session.query(WizarrUser).filter_by(token=token).first()
            # ...
            return user
    except Exception as e:
        logger.error(f"Database error during user lookup: {e}", exc_info=True)
        raise  # Re-raise critical errors
```

---

### 6. **MEDIUM: Secrets Visible in Error Messages**
**Location:** [backend/app/services/prowlarr_service.py](backend/app/services/prowlarr_service.py#L45), [backend/app/routers/downloads.py](backend/app/routers/downloads.py#L120)

**Issue:** Exception details are returned directly to clients in HTTP responses. If external services fail, sensitive information might leak:

```python
# In downloads.py (line 120)
except Exception as exc:
    raise HTTPException(status_code=502, detail=f"Prowlarr search failed: {exc}") from exc
```

If Prowlarr fails with a 403 error, the error message might include details about the API key validation failure.

```python
# In prowlarr_service.py - similar pattern
except Exception as exc:
    return {"connected": False, "error": str(exc)}
```

**Risk:** Information disclosure, attackers learn about infrastructure and credentials.

**Severity:** MEDIUM

**Remediation:**
```python
except Exception as exc:
    logger.error(f"Prowlarr search error: {exc}", exc_info=True)  # Log full error
    raise HTTPException(
        status_code=502, 
        detail="Search service unavailable"  # ← Generic message to client
    ) from exc
```

---

### 7. **MEDIUM: Weak CORS Configuration**
**Location:** [backend/app/main.py](backend/app/main.py#L32-L37)

**Issue:** CORS is configured with wildcard for methods and headers:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins_list,
    allow_credentials=True,  # ← Allows credentials with CORS
    allow_methods=["*"],      # ← Allows all methods
    allow_headers=["*"],      # ← Allows all headers
)
```

The `allow_credentials=True` combined with `allow_methods=["*"]` could allow:
- Preflight request abuse
- Unintended HTTP method access (TRACE, DELETE, etc.)

**Risk:** CORS bypass, unauthorized operations.

**Severity:** MEDIUM

**Remediation:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],  # ← Whitelist only needed methods
    allow_headers=["Authorization", "Content-Type"],     # ← Whitelist only needed headers
)
```

---

### 8. **MEDIUM: No Rate Limiting on Authentication Endpoint**
**Location:** [backend/app/routers/auth.py](backend/app/routers/auth.py#L80-L103)

**Issue:** The `/auth/login` endpoint has no rate limiting. An attacker can perform brute-force attacks against Wizarr tokens:

```python
@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login with a Wizarr token."""
    # No rate limiting!
    user = get_wizarr_user_by_token(request.wizarr_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid Wizarr token or user disabled")
```

**Risk:** Brute force attacks on user tokens, account takeover.

**Severity:** MEDIUM

**Remediation:**
```python
# Install: pip install slowapi

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter

@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")  # ← Max 5 login attempts per minute per IP
async def login(request: LoginRequest, request_obj: Request):
```

---

### 9. **MEDIUM: Masked Secrets Can Be Overwritten with Empty Values**
**Location:** [backend/app/routers/settings.py](backend/app/routers/settings.py#L60-L66)

**Issue:** The settings bulk update endpoint checks for `"***"` masked values to avoid overwriting, but doesn't prevent clearing secrets:

```python
@router.post("/bulk")
async def upsert_settings_bulk(body: dict, db: AsyncSession = Depends(get_db)):
    for key, value in body.items():
        # Skip masked values...
        if isinstance(value, str) and value.strip() == "***":
            continue
        # But empty strings are accepted!
        if row:
            row.value = str(value) if value is not None else None  # ← Can set to None
```

An attacker or misbehaving client could send `"value": ""` and clear critical API keys.

**Risk:** Denial of service by clearing integration credentials.

**Severity:** MEDIUM

**Remediation:**
```python
for key, value in body.items():
    if key not in ALLOWED_KEYS:
        continue
    
    # Guard sensitive settings from being cleared
    if "password" in key or "api_key" in key:
        if not value or value.strip() == "***":
            continue  # Don't allow clearing sensitive values
    
    # ... rest of logic
```

---

### 10. **MEDIUM: No HTTPS Enforcement**
**Location:** [backend/app/config.py](backend/app/config.py)

**Issue:** The application doesn't enforce HTTPS. All credentials (JWT tokens, API keys, passwords) are transmitted in plaintext if deployed over HTTP.

**Risk:** Man-in-the-middle attacks, credential interception.

**Severity:** MEDIUM

**Remediation:**
- Deploy behind HTTPS reverse proxy (nginx, Caddy)
- Add HSTS headers:

```python
app.add_middleware(
    BaseHTTPMiddleware,
    validate_request_scope=False
)

# Or use a middleware like:
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
app.add_middleware(HTTPSRedirectMiddleware)  # ← Redirect HTTP to HTTPS
```

---

## 🟡 LOW SECURITY ISSUES

### 11. **LOW: No Authentication Audit Logging**
**Location:** [backend/app/routers/auth.py](backend/app/routers/auth.py)

**Issue:** All authentication events (login, logout, token validation failures) are silent. No logging makes it impossible to detect brute-force attacks or unauthorized access attempts.

**Remediation:** Add comprehensive logging:
```python
import logging
logger = logging.getLogger(__name__)

@router.post("/login")
async def login(request: LoginRequest):
    logger.info(f"Login attempt with token: {request.wizarr_token[:8]}...")
    user = get_wizarr_user_by_token(request.wizarr_token)
    if not user:
        logger.warning(f"Failed login attempt with invalid token")
        raise HTTPException(status_code=401, ...)
    logger.info(f"User {user.username} logged in successfully")
```

---

### 12. **LOW: Uncommon File Extensions Not Validated**
**Location:** [backend/app/services/smart_download_service.py](backend/app/services/smart_download_service.py#L16-L21)

**Issue:** The application downloads files with extensions from `FILE_EXTENSIONS` set, but doesn't validate actual file content. A `.epub` file could contain malicious code.

```python
FILE_EXTENSIONS = {
    ".epub", ".mobi", ".azw3", ".pdf",
    ".cbz", ".cbr", ".zip", ".rar",  # ← .zip and .rar can contain executables
}
```

**Risk:** Low - files are dropped into Calibre/Komga watch folders which should handle them safely, but no MIME type validation occurs.

**Remediation:** Consider adding MIME type validation:
```python
import magic
mime = magic.Magic(mime=True)
file_mime = mime.from_file(downloaded_file)
if file_mime not in ALLOWED_MIMES:
    raise ValueError(f"Unsupported file type: {file_mime}")
```

---

### 13. **LOW: No Request/Response Size Limits**
**Location:** [backend/app/main.py](backend/app/main.py)

**Issue:** FastAPI doesn't enforce request size limits by default. An attacker can send enormous payloads to cause memory exhaustion.

**Remediation:**
```python
from fastapi.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware

class SizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_upload_size: int):
        super().__init__(app)
        self.max_upload_size = max_upload_size
    
    async def dispatch(self, request, call_next):
        if request.method == "POST":
            if "content-length" in request.headers:
                content_length = int(request.headers["content-length"])
                if content_length > self.max_upload_size:
                    return JSONResponse(status_code=413)
        return await call_next(request)

app.add_middleware(SizeLimitMiddleware, max_upload_size=50*1024*1024)  # 50MB max
```

---

### 14. **LOW: Missing Content-Security-Policy Headers**
**Location:** Frontend integration

**Issue:** No CSP headers prevent cross-site scripting attacks. If frontend is served from the same domain, vulnerable React components could execute arbitrary scripts.

**Remediation:**
```python
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'"
        return response

app.add_middleware(SecurityHeadersMiddleware)
```

---

### 15. **LOW: Unnecessary Wizarr Token in JWT Payload**
**Location:** [backend/app/routers/auth.py](backend/app/routers/auth.py#L93-L100)

**Issue:** The Wizarr token is stored in the JWT payload:

```python
to_encode = {
    "wizarr_token": user.token,  # ← Sensitive data in JWT
    "sub": user.username,
    "exp": expire,
    "iat": datetime.now(timezone.utc),
}
```

JWTs are base64-encoded, not encrypted. While the signature prevents tampering, the payload is readable.

**Risk:** Information disclosure if JWT is captured.

**Remediation:** Only store user ID in JWT; look up full user data from Wizarr on each request:
```python
to_encode = {
    "user_id": user.id,
    "sub": user.username,
    "exp": expire,
}

# Then in get_current_user, fetch fresh data from Wizarr
```

---

## ✅ FUNCTIONALITY OVERVIEW

### Core Features

The application provides a unified media discovery and download platform:

1. **Book Search**
   - Open Library integration (free, no API key)
   - Google Books integration (optional API key for better quotas)
   - Searches by title, author, ISBN
   - Source: [backend/app/services/book_search.py](backend/app/services/book_search.py)

2. **Comic/Manga Search**
   - MangaDex (manga, no API key required)
   - ComicVine (Western comics, requires API key)
   - AniList (anime/manga metadata, no API key)
   - Source: [backend/app/services/comic_search.py](backend/app/services/comic_search.py)

3. **Watchlist Management**
   - Add/update/delete items to track
   - Track status: wanted, found, downloading, downloaded, failed
   - Attach notes and source information
   - Source: [backend/app/routers/watchlist.py](backend/app/routers/watchlist.py)

4. **Direct Downloads**
   - Download files directly from HTTP URLs
   - Mirror URL fallback support
   - Automatic file naming and extension detection
   - Destination folder configuration per content type
   - Source: [backend/app/services/download_service.py](backend/app/services/download_service.py)

5. **Smart Downloads (Multi-Source)**
   - Anna's Archive integration
   - Libgen integration
   - Fallback to Prowlarr torrent search
   - Automatic source switching
   - Source: [backend/app/services/smart_download_service.py](backend/app/services/smart_download_service.py)

6. **Integration Management**
   - Komga (comics/manga management via Wizarr auth)
   - Calibre-Web Automated (book auto-import via folder watch)
   - Prowlarr (torrent indexing)
   - qBittorrent (torrent downloads)
   - Runtime connection testing

### Service Integrations

| Service | Integration Type | Auth Method | Purpose |
|---------|------------------|-------------|---------|
| **Wizarr** | User DB Read | SQLite Direct | User authentication & tokens |
| **Komga** | REST API | Wizarr Auth | Comics/manga browsing & library scan |
| **Calibre-Web** | URL + Folder Watch | HTTP + Filesystem | Book import automation |
| **Prowlarr** | REST API | API Key | Torrent indexing & search |
| **qBittorrent** | REST API | Username/Password | Torrent downloading |
| **External APIs** | HTTP REST | API Keys (optional) | Book/comics metadata |

---

## 🐛 ERROR HANDLING ANALYSIS

### Adequate Error Handling
✅ Try-catch blocks in search endpoints  
✅ HTTPException for expected errors  
✅ Fallback values when external services fail  
✅ Database rollback on failed downloads  

### Missing Error Handling
❌ No timeout context for long-running downloads  
❌ No retry logic for transient failures (rate limits, network blips)  
❌ No dead-letter queue for failed downloads  
❌ Silent failures in smart_download_service (errors caught but logged minimally)

### Exception Examples

**Good:**
```python
try:
    results = await search_books(db, q, source=source, limit=limit)
    return {"query": q, "source": source, "total": len(results), "results": results}
except Exception as exc:
    raise HTTPException(status_code=502, detail=f"Search failed: {exc}") from exc
```

**Could Improve:**
```python
try:
    anna_urls = await _annas_archive_candidates(q)
    candidates.extend(...)
except Exception:  # ← Silent swallowing
    pass  # ← No logging or metrics
```

---

## 📊 DATABASE OPERATIONS ANALYSIS

### Async/Await Usage
✅ Proper async SQLAlchemy usage throughout  
✅ Correct session management with context managers  
✅ Proper commit/rollback behavior  

### Potential Issues
❌ No transaction isolation levels specified (defaults to "read committed")  
❌ No connection pooling configuration - could exhaust pool under high load  
❌ No query timeout limits - long-running queries could hang  
❌ No database backup/recovery mentioned in deployment

### Recommendations
```python
# In database.py - add connection pool settings:
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=20,  # ← Connection pool size
    max_overflow=10,  # ← Additional connections allowed
    pool_pre_ping=True,  # ← Verify connection before use
    pool_recycle=3600,  # ← Recycle connections after 1 hour
)
```

---

## 📁 FILE OPERATIONS ANALYSIS

### Download Path Resolution
**File:** [backend/app/services/download_service.py](backend/app/services/download_service.py)

**Current Implementation:**
```python
def _safe_filename(name: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name)  # ← Good: removes path chars
    name = re.sub(r"\s+", " ", name).strip()
    return name[:180] if name else "download"
```

✅ **Strengths:**
- Filename sanitization removes path separators
- Limits filename length to 180 characters
- Removes control characters

❌ **Weaknesses (see CRITICAL issue #2):**
- Destination folder itself is not validated
- No symlink attack protection
- No verification that destination is writable

### File Operations Risks

**Race Condition Risk:**
```python
os.makedirs(folder, exist_ok=True)  # ← Could change between this
# ... and ...
async with aiofiles.open(filepath, "wb") as f:  # ← And this
```

An attacker with filesystem access could create a malicious symlink between these operations.

**Recommended Protection:**
```python
os.makedirs(folder, exist_ok=True, mode=0o750)  # ← Restrictive permissions

# Validate before writing
import tempfile
import shutil

# Write to temp file first
with tempfile.NamedTemporaryFile(dir=folder, delete=False) as tmp:
    temp_path = tmp.name
    # ... download to temp_path ...

# Then move atomically
shutil.move(temp_path, filepath)
```

---

## 🔍 SEARCH FUNCTIONALITY ANALYSIS

### Book Search
- ✅ Multi-source search (Open Library, Google Books)
- ✅ Graceful degradation if one source fails
- ✅ Proper result mapping to consistent schema
- ⚠️ No caching of search results (repeated queries hit APIs)
- ⚠️ No rate limiting per user

### Comic Search
- ✅ Multi-source search (MangaDex, ComicVine, AniList)
- ✅ Proper pagination support
- ✅ GraphQL query construction
- ⚠️ ComicVine requires API key - fails silently if not configured
- ⚠️ No deduplication of results across sources

### Improvement Suggestions

**Add Result Caching:**
```python
from functools import lru_cache
import hashlib

@lru_cache(maxsize=1000)
async def cached_search(query_hash: str, source: str):
    # Cache for 1 hour
    return search_results
```

**Add Rate Limiting:**
```python
# Per-user rate limit on searches
@limiter.limit("100/hour")
@router.get("/search")
async def search(q: str, ...):
```

---

## 📋 SUMMARY TABLE

| Category | Status | Notes |
|----------|--------|-------|
| **Authentication** | ⚠️ At Risk | Weak default SECRET_KEY is critical |
| **Authorization** | ✅ Good | JWT-based, properly enforced on routes |
| **Input Validation** | ⚠️ Partial | Basic validation, no ReDoS protection |
| **Secrets Handling** | ⚠️ Risky | Stored in DB, masked but not encrypted |
| **CORS** | ⚠️ Weak | Too permissive, should whitelist methods/headers |
| **Path Traversal** | 🔴 Critical | Destination validation missing |
| **Logging/Audit** | ❌ Missing | No authentication audit trail |
| **Rate Limiting** | ❌ Missing | No protection on sensitive endpoints |
| **HTTPS** | ⚠️ Not Enforced | Depends on deployment environment |
| **Database** | ✅ Good | Proper async handling, could pool better |
| **Error Handling** | ✅ Adequate | Good try-catch, but some silent failures |
| **File Operations** | 🔴 Critical | Path traversal risks |
| **Search Features** | ✅ Good | Multi-source, graceful degradation |

---

## 🎯 PRIORITIZED REMEDIATION ROADMAP

### Phase 1: CRITICAL (Do Immediately)
1. **Generate strong SECRET_KEY** - Production deployment blockers
2. **Fix path traversal in downloads** - Security vulnerability
3. **Fail at startup if critical env vars missing**

### Phase 2: MEDIUM (Before Production)
1. Add rate limiting to auth endpoints
2. Implement proper input validation on search queries
3. Add security headers middleware
4. Implement comprehensive logging
5. Validate secret settings to prevent clearing via API

### Phase 3: NICE-TO-HAVE (Hardening)
1. Implement request size limits
2. Add database connection pooling optimization
3. Implement search result caching
4. Add encrypted secrets storage (instead of plaintext DB)
5. Implement retry logic with exponential backoff

---

## 🔒 DEPLOYMENT SECURITY CHECKLIST

- [ ] Generate new `SECRET_KEY` (min 32 bytes random)
- [ ] Set all required environment variables
- [ ] Deploy behind HTTPS reverse proxy
- [ ] Configure firewall to only expose necessary ports
- [ ] Enable database encryption at rest (if possible)
- [ ] Set up log aggregation and monitoring
- [ ] Implement automated backups
- [ ] Set restrictive file permissions (750 for directories, 640 for files)
- [ ] Disable DEBUG mode in production
- [ ] Implement regular security scanning

---

## 📞 CONCLUSION

GhostShelf demonstrates solid architectural decisions with FastAPI, async/await patterns, and multi-service integration. However, **two critical security vulnerabilities must be addressed before production deployment:**

1. **Hardcoded SECRET_KEY** - Allows JWT forgery
2. **Path traversal in downloads** - Allows arbitrary file write

Additionally, **eight medium-severity issues** should be resolved to harden the application against attacks. The functionality is comprehensive and well-structured, with good error handling in most areas.

**Recommendation:** Implement Phase 1 fixes immediately, Phase 2 fixes before production, and Phase 3 for ongoing hardening.

---

**Report Generated:** March 22, 2026  
**Audit Scope:** Full codebase analysis  
**Version:** 1.0.0
