# ============================================================================
# DATABASE SETUP GUIDE - Ghost Backend Framework
# ============================================================================

## PostgreSQL Setup (Recommended for Production)

### 1. Install PostgreSQL

#### macOS:
```bash
# Using Homebrew
brew install postgresql
brew services start postgresql

# Using MacPorts  
# Default package install form (client + server)
sudo port install postgresql16 postgresql16-server
# Ensure psql points to v16
sudo port select --set postgresql postgresql16
# Initialize cluster (first time only)
sudo -u postgres /opt/local/lib/postgresql16/bin/initdb \
  -D /opt/local/var/db/postgresql16/defaultdb \
  -A scram-sha-256 \
  -U postgres
# Start now and on login
sudo port load postgresql16-server
```

#### Ubuntu/Debian:
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### CentOS/RHEL:
```bash
sudo yum install postgresql-server postgresql-contrib
sudo postgresql-setup initdb
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### 2. Create Database and User
```bash
# Connect to PostgreSQL as postgres user
sudo -u postgres psql

# Create your database
CREATE DATABASE myapp_db;

# Create user with password
CREATE USER myapp_user WITH ENCRYPTED PASSWORD 'your_secure_password';

# Grant privileges
GRANT ALL PRIVILEGES ON DATABASE myapp_db TO myapp_user;
GRANT ALL ON SCHEMA public TO myapp_user;

# For PostgreSQL 15+
GRANT CREATE ON SCHEMA public TO myapp_user;

# Exit
\q
```

### 3. Configure PostgreSQL for Remote Connections (if needed)

Edit PostgreSQL configuration files:

#### postgresql.conf:
```ini
# Listen on all addresses (be careful in production)
listen_addresses = '*'

# Or specific IP
listen_addresses = 'localhost,192.168.1.100'

# Connection limits
max_connections = 200
```

#### pg_hba.conf:
```
# Allow connections from your app server
host    myapp_db    myapp_user    192.168.1.0/24    md5

# For local development
host    myapp_db    myapp_user    127.0.0.1/32      md5
```

### 4. Test Connection
```bash
# Test connection
psql -h localhost -U myapp_user -d myapp_db

# Or with connection string
psql "postgresql://myapp_user:your_secure_password@localhost:5432/myapp_db"
```

## Redis Setup (Optional - for Caching and Sessions)

### 1. Install Redis

#### macOS:
```bash
brew install redis
brew services start redis
```

#### Ubuntu/Debian:
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

### 2. Configure Redis Security

Edit `/etc/redis/redis.conf`:
```ini
# Bind to specific interface (not 0.0.0.0 in production)
bind 127.0.0.1

# Set password (uncomment and set a strong password)
requirepass your_redis_password

# Disable dangerous commands in production
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command DEBUG ""
```

### 3. Test Redis Connection
```bash
redis-cli
# If password protected:
redis-cli -a your_redis_password

# Test
ping
# Should return: PONG
```

## MongoDB Setup (Optional - for Document Storage)

### 1. Install MongoDB

#### macOS:
```bash
# Add MongoDB tap
brew tap mongodb/brew

# Install MongoDB Community Edition
brew install mongodb-community
brew services start mongodb-community
```

#### Ubuntu/Debian:
```bash
# Import MongoDB GPG key
wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | sudo apt-key add -

# Add MongoDB repository
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/6.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list

# Install MongoDB
sudo apt update
sudo apt install mongodb-org

# Start MongoDB
sudo systemctl start mongod
sudo systemctl enable mongod
```

### 2. Configure MongoDB Security
```bash
# Connect to MongoDB
mongosh

# Create admin user
use admin
db.createUser({
  user: "admin",
  pwd: "your_admin_password",
  roles: ["userAdminAnyDatabase", "dbAdminAnyDatabase", "readWriteAnyDatabase"]
})

# Create application user
use myapp_db
db.createUser({
  user: "myapp_user",
  pwd: "your_app_password",
  roles: ["readWrite"]
})
```

Edit `/etc/mongod.conf`:
```yaml
security:
  authorization: enabled

net:
  bindIp: 127.0.0.1  # Change as needed
  port: 27017
```

## SQLite Setup (for Development/Testing)

SQLite requires no installation - it's included with Python.

### Configuration:
```env
DB_DRIVER=sqlite
DB_NAME=myapp.db  # Will be created automatically
```

## Environment-Specific Database URLs

### Development (.env):
```env
# PostgreSQL
DATABASE_URL=postgresql://myapp_user:your_secure_password@localhost:5432/myapp_db

# SQLite
DATABASE_URL=sqlite:///./myapp.db

# Redis
REDIS_URL=redis://:your_redis_password@localhost:6379/0

# MongoDB
MONGODB_URL=mongodb://myapp_user:your_app_password@localhost:27017/myapp_db
```

### Production (.env):
```env
# PostgreSQL with SSL
DATABASE_URL=postgresql://myapp_user:your_secure_password@prod-db.example.com:5432/myapp_db?sslmode=require

# Redis with password
REDIS_URL=redis://:your_redis_password@redis.example.com:6379/0

# MongoDB with authentication
MONGODB_URL=mongodb://myapp_user:your_app_password@mongo.example.com:27017/myapp_db?authSource=myapp_db&ssl=true
```

## Database Migration Setup

Your Ghost Backend Framework includes Alembic for database migrations.

### 1. Initialize Alembic (if not done):
```bash
cd /Users/grayghostdataconsultants/Ghost
alembic init alembic
```

### 2. Configure alembic.ini:
```ini
# Point to your database
sqlalchemy.url = postgresql://myapp_user:your_secure_password@localhost:5432/myapp_db

# Or use environment variable
sqlalchemy.url = driver://user:pass@localhost/dbname
```

### 3. Create and Run Migrations:
```bash
# Create a new migration
alembic revision --autogenerate -m "Create initial tables"

# Apply migrations
alembic upgrade head

# Check current version
alembic current

# View migration history
alembic history
```

## Database Performance Optimization

### PostgreSQL Optimization:
```sql
-- Add indexes for frequently queried columns
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_posts_created_at ON posts(created_at);

-- For full-text search
CREATE INDEX idx_posts_search ON posts USING GIN(to_tsvector('english', title || ' ' || content));

-- Monitor slow queries
ALTER SYSTEM SET log_min_duration_statement = 1000;  -- Log queries > 1 second
```

### Connection Pooling Settings:
```env
# In your .env file
DB_POOL_SIZE=20          # Number of connections to maintain
DB_MAX_OVERFLOW=30       # Additional connections when needed
DB_POOL_TIMEOUT=30       # Seconds to wait for connection
DB_POOL_RECYCLE=3600     # Seconds before reconnecting
```

## Backup and Recovery

### PostgreSQL Backup:
```bash
# Full database backup
pg_dump -h localhost -U myapp_user myapp_db > backup.sql

# Compressed backup
pg_dump -h localhost -U myapp_user myapp_db | gzip > backup.sql.gz

# Restore from backup
psql -h localhost -U myapp_user myapp_db < backup.sql
```

### Redis Backup:
```bash
# Redis automatically saves to dump.rdb
# Force save
redis-cli BGSAVE

# Copy the RDB file
cp /var/lib/redis/dump.rdb /backup/location/
```

## Health Checks

Your Ghost Backend Framework includes database health checks:

```python
# Example health check endpoint
from ghost import DatabaseManager

@app.get("/health")
async def health_check():
    db_manager = DatabaseManager(config.database)
    db_healthy = await db_manager.health_check()
    
    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "database": db_healthy,
        "timestamp": datetime.utcnow()
    }
```

## Troubleshooting Common Issues

### 1. Connection Refused:
- Check if database service is running
- Verify host/port configuration
- Check firewall settings

### 2. Authentication Failed:
- Verify username/password
- Check user permissions
- Ensure database exists

### 3. SSL/TLS Issues:
- Check SSL mode configuration
- Verify certificates
- Update connection string with SSL parameters

### 4. Performance Issues:
- Monitor connection pool usage
- Check for missing indexes
- Analyze slow query logs
- Consider read replicas for high-read workloads

Remember to always use strong passwords and enable SSL/TLS in production!
