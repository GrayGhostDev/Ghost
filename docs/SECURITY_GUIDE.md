# ============================================================================
# SECURITY CONFIGURATION GUIDE - Ghost Backend Framework
# ============================================================================

## 🔑 JWT Token Configuration

### 1. Generate a Secure JWT Secret Key

**CRITICAL**: Never use the default or example keys in production!

```bash
# Generate a 256-bit (64 character) random key
python -c "import secrets; print(secrets.token_urlsafe(64))"

# Alternative using OpenSSL
openssl rand -base64 64

# Alternative using Node.js
node -e "console.log(require('crypto').randomBytes(64).toString('base64'))"
```

### 2. JWT Configuration in .env:
```env
# REQUIRED: Replace with your generated key
JWT_SECRET_KEY=your-generated-64-character-random-key-here-replace-this-immediately
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30      # Short-lived access tokens
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7         # Longer-lived refresh tokens
```

## 🛡️ Password Security

### 1. Password Hashing Configuration:
```env
# Bcrypt rounds (higher = more secure but slower)
BCRYPT_ROUNDS=12                        # 12-14 recommended for production

# Password requirements
PASSWORD_MIN_LENGTH=8
PASSWORD_REQUIRE_UPPERCASE=true
PASSWORD_REQUIRE_LOWERCASE=true
PASSWORD_REQUIRE_NUMBERS=true
PASSWORD_REQUIRE_SPECIAL=true
```

### 2. Password Validation Example:
```python
from ghost import AuthManager, ValidationUtils

auth_manager = AuthManager(config.auth)
validator = ValidationUtils()

# Validate password strength
def validate_password(password: str) -> bool:
    return validator.is_strong_password(
        password,
        min_length=8,
        require_uppercase=True,
        require_lowercase=True,
        require_numbers=True,
        require_special=True
    )

# Hash password before storing
hashed_password = auth_manager.hash_password("user_password")
```

## 🔒 API Security

### 1. API Key Management:
```env
# Generate API keys for service-to-service communication
API_KEY=api_key_$(openssl rand -hex 32)

# Rate limiting to prevent abuse
API_RATE_LIMIT=100/minute               # Adjust based on your needs
API_BURST_LIMIT=200/minute              # Allow brief bursts

# Request size limits
API_MAX_REQUEST_SIZE=10485760           # 10MB limit
API_REQUEST_TIMEOUT=30                  # 30 second timeout
```

### 2. CORS Configuration:
```env
# CORS settings for frontend integration
API_CORS_ORIGINS=["https://yourdomain.com","https://www.yourdomain.com"]
API_CORS_METHODS=["GET","POST","PUT","DELETE","PATCH"]
API_CORS_HEADERS=["Content-Type","Authorization"]
API_CORS_CREDENTIALS=true
```

## 🌐 HTTPS and SSL/TLS

### 1. Force HTTPS in Production:
```env
# Force HTTPS redirects
FORCE_HTTPS=true
HSTS_MAX_AGE=31536000                   # 1 year HSTS
HSTS_INCLUDE_SUBDOMAINS=true
HSTS_PRELOAD=true
```

### 2. SSL Certificate Setup:
```bash
# Using Let's Encrypt with Certbot
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Or using Cloudflare Origin Certificates
# Download certificates and configure in your reverse proxy
```

### 3. Database SSL Configuration:
```env
# PostgreSQL with SSL
DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require

# For self-signed certificates
DATABASE_SSL_MODE=require
DATABASE_SSL_CERT=/path/to/client-cert.pem
DATABASE_SSL_KEY=/path/to/client-key.pem  
DATABASE_SSL_ROOT_CERT=/path/to/ca-cert.pem
```

## 🚨 Environment Security

### 1. Environment Variable Security:
```bash
# Set restrictive permissions on .env file
chmod 600 .env

# Never commit .env to version control
echo ".env" >> .gitignore
echo "*.env" >> .gitignore
echo ".env.*" >> .gitignore
```

### 2. Secrets Management (Production):
```bash
# Using AWS Secrets Manager
aws secretsmanager create-secret --name "myapp/database" --secret-string '{"password":"your_db_password"}'

# Using Azure Key Vault
az keyvault secret set --vault-name "MyKeyVault" --name "database-password" --value "your_db_password"

# Using Google Secret Manager
echo -n "your_db_password" | gcloud secrets create database-password --data-file=-
```

## 🔍 Input Validation and Sanitization

### 1. Request Validation:
```python
from ghost import ValidationUtils
from pydantic import BaseModel, validator

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    
    @validator('email')
    def validate_email(cls, v):
        validator = ValidationUtils()
        if not validator.is_email(v):
            raise ValueError('Invalid email format')
        return v.lower()
    
    @validator('username') 
    def validate_username(cls, v):
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username can only contain letters, numbers, hyphens, and underscores')
        return v
```

### 2. SQL Injection Prevention:
```python
# Ghost Framework uses SQLAlchemy ORM which prevents SQL injection
# Always use parameterized queries:

# GOOD (SQLAlchemy ORM)
user = session.query(User).filter(User.email == email).first()

# GOOD (SQLAlchemy Core with parameters)
result = session.execute(
    text("SELECT * FROM users WHERE email = :email"),
    {"email": email}
)

# NEVER do this (vulnerable to SQL injection)
# query = f"SELECT * FROM users WHERE email = '{email}'"
```

## 🛡️ Authorization and Access Control

### 1. Role-Based Access Control (RBAC):
```python
from ghost import AuthManager, User, UserRole

# Define user roles
class CustomUserRole(UserRole):
    ADMIN = "admin"
    MANAGER = "manager" 
    USER = "user"
    READONLY = "readonly"

# Check permissions
def require_admin(current_user: User):
    if CustomUserRole.ADMIN not in current_user.roles:
        raise HTTPException(status_code=403, detail="Admin access required")

# Use in FastAPI endpoints
@app.get("/admin/users")
async def list_users(current_user: User = Depends(get_current_user)):
    require_admin(current_user)
    # Admin-only logic here
```

### 2. Resource-Level Permissions:
```python
# Example: Users can only access their own data
@app.get("/users/{user_id}")
async def get_user(user_id: str, current_user: User = Depends(get_current_user)):
    # Check if user can access this resource
    if user_id != current_user.id and CustomUserRole.ADMIN not in current_user.roles:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Fetch and return user data
    return await get_user_by_id(user_id)
```

## 🔐 Session Security

### 1. Secure Session Configuration:
```env
# Session settings
SESSION_SECRET_KEY=your-session-secret-key-different-from-jwt-key
SESSION_COOKIE_SECURE=true              # HTTPS only
SESSION_COOKIE_HTTPONLY=true            # No JavaScript access
SESSION_COOKIE_SAMESITE=strict          # CSRF protection
SESSION_COOKIE_MAX_AGE=1800             # 30 minutes
```

### 2. Token Blacklisting:
```python
# Example token blacklist implementation
class TokenBlacklist:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def blacklist_token(self, token: str, expiry: int):
        """Add token to blacklist"""
        await self.redis.setex(f"blacklist:{token}", expiry, "1")
    
    async def is_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted"""
        return await self.redis.exists(f"blacklist:{token}")
```

## 🔍 Logging and Monitoring Security Events

### 1. Security Event Logging:
```env
# Security-specific logging
LOG_SECURITY_EVENTS=true
SECURITY_LOG_FILE=logs/security.log

# Log failed login attempts
LOG_FAILED_LOGINS=true
MAX_LOGIN_ATTEMPTS=5
LOGIN_LOCKOUT_DURATION=1800             # 30 minutes
```

### 2. Example Security Logger:
```python
from ghost import get_logger

security_logger = get_logger("security")

# Log security events
async def log_login_attempt(username: str, ip: str, success: bool):
    security_logger.info(
        "Login attempt",
        extra={
            "event_type": "login_attempt",
            "username": username,
            "ip_address": ip,
            "success": success,
            "timestamp": datetime.utcnow()
        }
    )

# Log suspicious activities
async def log_suspicious_activity(user_id: str, activity: str, details: dict):
    security_logger.warning(
        "Suspicious activity detected",
        extra={
            "event_type": "suspicious_activity",
            "user_id": user_id,
            "activity": activity,
            "details": details,
            "timestamp": datetime.utcnow()
        }
    )
```

## 🛡️ Production Security Checklist

### Before Deployment:
- [ ] Changed all default passwords and secret keys
- [ ] Generated strong JWT secret key (64+ characters)
- [ ] Configured HTTPS with valid SSL certificates
- [ ] Set up proper CORS policies
- [ ] Configured rate limiting
- [ ] Set secure file permissions on .env (600)
- [ ] Enabled database SSL connections
- [ ] Set up proper backup encryption
- [ ] Configured security headers (HSTS, CSP, etc.)
- [ ] Set up monitoring and alerting for security events
- [ ] Implemented proper error handling (no sensitive info in errors)
- [ ] Set up log rotation and secure log storage
- [ ] Configured firewall rules
- [ ] Set up intrusion detection/prevention
- [ ] Implemented proper session management
- [ ] Set up secrets management system
- [ ] Configured security scanning in CI/CD pipeline

### Regular Security Maintenance:
- [ ] Rotate JWT secret keys periodically
- [ ] Update dependencies regularly
- [ ] Monitor security logs for anomalies
- [ ] Conduct security audits
- [ ] Test backup and recovery procedures
- [ ] Review and update access permissions
- [ ] Update SSL certificates before expiration

## 🚨 Security Incident Response

### 1. Incident Detection:
```python
# Example security monitoring
class SecurityMonitor:
    def __init__(self, auth_manager, logger):
        self.auth_manager = auth_manager
        self.logger = logger
    
    async def detect_brute_force(self, ip: str) -> bool:
        """Detect brute force attacks"""
        failed_attempts = await self.get_failed_attempts(ip, minutes=15)
        if failed_attempts > 10:
            await self.block_ip(ip, duration=3600)  # 1 hour
            self.logger.critical(f"Brute force attack detected from {ip}")
            return True
        return False
```

### 2. Automatic Response:
```python
# Example automatic security responses
async def handle_security_incident(incident_type: str, details: dict):
    if incident_type == "brute_force":
        # Block IP automatically
        await block_ip(details["ip"], duration=3600)
        
    elif incident_type == "token_compromise": 
        # Invalidate all user tokens
        await invalidate_user_tokens(details["user_id"])
        
    # Always notify administrators
    await send_security_alert(incident_type, details)
```

Remember: Security is an ongoing process, not a one-time setup. Regularly review and update your security configurations!
