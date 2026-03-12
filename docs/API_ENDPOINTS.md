# API Endpoints Reference

Built-in routes provided by the Ghost Backend framework (`src/ghost/api.py`).

## Routes

| Method | Path | Auth | Rate Limit | Description |
|--------|------|------|------------|-------------|
| GET | `/` | No | None | Root endpoint — returns project name and version |
| GET | `/health` | No | None | Health check — reports API, database, and Redis status |
| GET | `/metrics` | No | 30/min | Prometheus-format metrics (falls back to JSON if prometheus-client not installed) |
| POST | `/token` | No | 5/min | Token endpoint stub — returns 501; override in Level 3 |
| POST | `/login` | No | 5/min | Login endpoint stub — returns 501; override in Level 3 |
| POST | `/forgot-password` | No | 3/min | Password reset request — always returns 200 to prevent email enumeration |
| POST | `/reset-password` | No | 5/min | Validate reset token and return verified user_id |

## Response Format

All endpoints return the standardized `APIResponse` format:

### Success

```json
{
  "success": true,
  "message": "Success",
  "data": { ... },
  "timestamp": 1710000000.0
}
```

### Error

```json
{
  "success": false,
  "message": "Error description",
  "error": {
    "code": 400,
    "details": {}
  },
  "timestamp": 1710000000.0
}
```

### Paginated

```json
{
  "success": true,
  "message": "Success",
  "data": [ ... ],
  "meta": {
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 100,
      "pages": 5
    }
  },
  "timestamp": 1710000000.0
}
```

## Password Reset Flow

### `POST /forgot-password`

**Request:**
```json
{ "email": "user@example.com" }
```

**Response (always 200):**
```json
{
  "success": true,
  "message": "If an account with that email exists, a reset link has been sent."
}
```

### `POST /reset-password`

**Request:**
```json
{
  "token": "<JWT reset token>",
  "new_password": "new-secure-password"
}
```

**Success Response (200):**
```json
{
  "success": true,
  "message": "Password reset token verified. Level 3 consumer should update the password.",
  "data": { "user_id": "user-42" }
}
```

**Error Response (400):**
```json
{
  "detail": "Invalid or expired reset token"
}
```

## Response Headers

All responses include:

| Header | Description |
|--------|-------------|
| `X-Request-ID` | Unique UUID for request tracing |
| `X-Process-Time` | Request processing duration in seconds |

## Rate Limiting

Rate limits use [SlowAPI](https://github.com/laurentS/slowapi) with `get_remote_address` key function. When exceeded, returns HTTP 429.
