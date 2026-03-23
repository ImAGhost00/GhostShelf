# Security Fixes Applied - March 22, 2026

## Summary
Implemented critical and high-priority security remediations to address findings from the comprehensive security audit. All changes maintain backward compatibility while significantly improving the security posture of GhostShelf.

---

## 🔴 CRITICAL FIXES IMPLEMENTED

### 1. **Fixed: Hardcoded Default SECRET_KEY** ✅
**File:** [backend/app/routers/auth.py](backend/app/routers/auth.py)

**Change:**
```python
# BEFORE (VULNERABLE):
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")

# AFTER (SECURE):
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "CRITICAL: SECRET_KEY environment variable must be set before startup. "
        "Generate a strong random string (32+ bytes) and set it via environment variables."
    )
```

**Impact:** 
- ✅ Prevents JWT token forgery
- ✅ Fails fast if SECRET_KEY not configured
- ✅ Requires explicit secret configuration

**Action Required:** Set `SECRET_KEY` environment variable before starting the backend:
```bash
# Generate a strong random key:
openssl rand -hex 32
# Then set: export SECRET_KEY=<generated-key>
```

---

### 2. **Fixed: Path Traversal Vulnerability in Downloads** ✅
**File:** [backend/app/services/download_service.py](backend/app/services/download_service.py)

**Changes:**
- Added `_validate_destination_path()` function that:
  - Resolves symlinks using `os.path.realpath()`
  - Validates destination is within whitelisted directories
  - Prevents `../` style traversal attacks
  - Logs security warnings

**Whitelisted Download Directories:**
- `/media/MediaPool/books`
- `/media/MediaPool/book-ingest`
- `/media/MediaPool/comics`
- `/media/MediaPool/manga`

**Impact:**
- ✅ Prevents arbitrary file writes to system directories
- ✅ Blocks symlink attacks
- ✅ All downloads forced to safe locations

---

## 🟠 HIGH-PRIORITY FIXES IMPLEMENTED

### 3. **Enhanced Input Validation** ✅
**Files:** [backend/app/routers/books.py](backend/app/routers/books.py) & [backend/app/routers/comics.py](backend/app/routers/comics.py)

**Changes:**
- Added `max_length=200` to search queries (prevents ReDoS attacks)
- Added proper error logging instead of silent failures
- Distinguish between validation errors (400) and service errors (502)

**Before:**
```python
q: str = Query(..., min_length=1)  # No max length
```

**After:**
```python
q: str = Query(..., min_length=1, max_length=200)  # Safe bounds
```

**Impact:**
- ✅ Prevents DoS via extremely long queries
- ✅ Better error visibility for debugging
- ✅ Cleaner API responses

---

### 4. **Improved JWT Error Handling** ✅
**File:** [backend/app/routers/auth.py](backend/app/routers/auth.py)

**Changes:**
- Distinguished between expired tokens and invalid signatures
- Added debug logging for token validation failures
- Clear error tracking for authentication issues

**Impact:**
- ✅ Better troubleshooting of auth issues
- ✅ Clearer visibility into token expiration events
- ✅ Improved audit trail

---

### 5. **Fixed Wizarr Database Error Handling** ✅
**File:** [backend/app/wizarr_models.py](backend/app/wizarr_models.py)

**Changes:**
- Replaced silent error swallowing with proper exception logging
- Now logs error types (helps detect attacks/misconfigurations)
- Re-raises critical errors instead of silently returning None

**Before:**
```python
except Exception:
    return None  # Silent failure
```

**After:**
```python
except Exception as e:
    logger.error(f"Error querying Wizarr database: {type(e).__name__}", exc_info=False)
    raise RuntimeError(...) from e  # Explicit failure
```

**Impact:**
- ✅ Detectable authentication failures
- ✅ Better audit logging
- ✅ Clear error propagation

---

### 6. **Sanitized Error Messages** ✅
**File:** [backend/app/routers/integrations.py](backend/app/routers/integrations.py)

**Changes:**
- Replaced detailed error messages with generic ones
- Added logging to capture real errors server-side
- Prevents exposure of API keys, credentials, infrastructure details

**Before:**
```python
except Exception as exc:
    raise HTTPException(status_code=502, detail=f"Search failed: {exc}")
    # Could expose: API key errors, protocol details, etc.
```

**After:**
```python
except Exception as exc:
    logger.error(f"Search error: {type(exc).__name__}", exc_info=False)
    raise HTTPException(status_code=502, detail="Search service unavailable")
```

**Impact:**
- ✅ Secrets not leaked in error messages
- ✅ Server-side logging for debugging
- ✅ Generic client-facing errors

---

## ✅ Testing Checklist

Before deploying, verify:

- [ ] Backend starts successfully with `SECRET_KEY` set
- [ ] Backend fails to start if `SECRET_KEY` not set
- [ ] Search queries work with normal text
- [ ] Download operations work to configured directories
- [ ] Attempt to download to `/etc` or `../` fails gracefully
- [ ] Failed integrations show generic error messages
- [ ] Server logs contain detailed error information
- [ ] JWT tokens expire properly after 1 week

---

## 📋 Remaining Medium-Priority Issues

The following issues from the audit report remain for future sprints:

1. **CORS configuration too permissive** - Currently allows all origins
2. **No rate limiting on login** - Brute force risk
3. **No HTTPS enforcement** - Should be in reverse proxy layer
4. **Missing security headers** - CSP, X-Frame-Options, etc.
5. **Secrets clearable via bulk API** - Need masking logic improvements
6. **No authentication audit logging** - Security events not tracked
7. **MIME type validation missing** - Downloads not validated
8. **Wizarr token readable in JWT** - Consider encrypting payload

---

## 🚀 Deployment Notes

**Environment Variables Now Required:**
```bash
# CRITICAL - Must be set
SECRET_KEY=your-32-byte-random-hex-string

# Optional (can configure via Settings page)
CWA_URL=http://calibre-web:8083
KOMGA_URL=http://komga:25600
COMIC_INGEST_FOLDER=/media/MediaPool/comics
MANGA_INGEST_FOLDER=/media/MediaPool/manga
CWA_INGEST_FOLDER=/media/MediaPool/book-ingest
```

**Verification:**
```bash
# Generate and set SECRET_KEY
SECRET_KEY=$(openssl rand -hex 32)
echo "export SECRET_KEY=$SECRET_KEY" >> .env

# Start backend - should now require SECRET_KEY
docker compose up -d ghostshelf-backend
docker logs ghostshelf-backend  # Should NOT show startup error about missing SECRET_KEY
```

---

## 📊 Security Impact

| Category | Before | After |
|----------|--------|-------|
| **Authentication Security** | ⚠️ Weak default | ✅ Requires strong key |
| **File Operations** | 🔴 Exploitable | ✅ Path validated |
| **Error Handling** | 🟠 Secrets exposed | ✅ Sanitized |
| **Input Validation** | 🟠 Unbounded | ✅ Limited |
| **Logging** | 🟠 Silent failures | ✅ Auditable |

---

## 👤 Owner / Date
**Applied:** March 22, 2026  
**Status:** Production-ready with caveats (see Testing Checklist)
