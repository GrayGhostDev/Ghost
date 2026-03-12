# Error Codes Reference

HTTP status codes and error patterns used by the Ghost Backend framework.

## HTTP Status Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| 200 | OK | Successful request, health check, forgot-password (always) |
| 400 | Bad Request | Invalid JSON payload, missing required fields, invalid reset token, validation errors |
| 401 | Unauthorized | Missing or invalid authentication token, invalid API key |
| 404 | Not Found | Resource not found (application-defined) |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Unhandled exceptions |
| 501 | Not Implemented | Stub endpoints (`/token`, `/login`) awaiting Level 3 implementation |

## Error Response Format

All errors follow the `APIResponse.error()` format:

```json
{
  "success": false,
  "message": "<human-readable description>",
  "error": {
    "code": <HTTP status code>,
    "details": { ... }
  },
  "timestamp": <unix epoch float>
}
```

## Framework Error Patterns

### Authentication Errors (401)

| Message | Cause |
|---------|-------|
| `"Invalid authentication token"` | JWT verification failed or token expired |
| `"API key required"` | No API key provided to protected endpoint |
| `"Invalid API key"` | API key JWT verification failed |

### Validation Errors (400)

| Message | Cause |
|---------|-------|
| `"Invalid JSON payload"` | Request body is not valid JSON |
| `"Missing required fields: field1, field2"` | Required fields absent from payload |
| `"Both 'token' and 'new_password' are required"` | Reset password missing fields |
| `"Invalid or expired reset token"` | Password reset JWT failed verification |
| `"File type not allowed: filename"` | Upload rejected by extension filter |
| `"File too large: N bytes (max: M)"` | Upload exceeds size limit |

### Rate Limit Errors (429)

| Message | Cause |
|---------|-------|
| `"Rate limit exceeded"` | SlowAPI rate limit hit |

### Server Errors (500)

| Message | Cause |
|---------|-------|
| `"Internal server error"` | Unhandled exception caught by global handler |

### Stub Errors (501)

| Message | Cause |
|---------|-------|
| `"Token endpoint not yet implemented..."` | `/token` stub |
| `"Login endpoint not yet implemented..."` | `/login` stub |

## Exception Handler Chain

The framework registers three global exception handlers (in order of specificity):

1. **`HTTPException`** — Returns the exception's status code and detail as `APIResponse.error()`
2. **`ValueError`** — Returns 400 with the exception message
3. **`Exception`** (catch-all) — Logs the full traceback, returns 500 with generic message
