# Port Configuration and Network Security Guide

## Overview

This document provides comprehensive guidance on port configuration, network security, and deployment best practices for the Ghost Backend Framework.

## Port Configuration Strategy

### Development Environment
- **API Server**: 127.0.0.1:8000 (primary), 127.0.0.1:8001 (alternative)
- **PostgreSQL**: 127.0.0.1:5432
- **Redis**: 127.0.0.1:6379
- **MongoDB**: 127.0.0.1:27017 (if used)

### Production Environment
- **API Server**: 127.0.0.1:8080 (behind reverse proxy)
- **Public Access**: 443 (HTTPS), 80 (redirects to HTTPS)
- **All services**: Bound to localhost only

### Docker Environment
- **Container Internal**: 0.0.0.0:8888 (OK within container)
- **Host Binding**: 127.0.0.1:8888 (secure host exposure)
- **Inter-container**: Via Docker network names

## Security Best Practices

### 1. Never Expose Services Directly

❌ **INCORRECT** (Security Risk):
```yaml
# docker-compose.yml
ports:
  - "8888:8888"  # Exposes to all network interfaces
```

✅ **CORRECT** (Secure):
```yaml
# docker-compose.yml
ports:
  - "127.0.0.1:8888:8888"  # Only localhost
```

### 2. Use Reverse Proxy for External Access

All external traffic should go through a reverse proxy (nginx/traefik):
```
Internet → Firewall → Reverse Proxy (443) → Backend (127.0.0.1:8080)
```

### 3. Firewall Configuration

```bash
# UFW (Ubuntu Firewall) Configuration
# Allow SSH (restrict to specific IPs)
ufw allow from 203.0.113.0/24 to any port 22

# Allow HTTP/HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# Block direct API access
ufw deny 8080/tcp
ufw deny 8000/tcp
ufw deny 8888/tcp

# Block database ports
ufw deny 5432/tcp
ufw deny 6379/tcp
ufw deny 27017/tcp

# Enable firewall
ufw enable
```

## SSH Configuration (Deployment)

### Why No SSH Configuration Files?

The Ghost Backend Framework intentionally **does not include SSH configuration files** for security reasons:

1. **Security**: SSH keys should never be committed to repositories
2. **Flexibility**: Each deployment environment has unique SSH requirements
3. **Best Practice**: SSH configuration should be managed separately from application code

### Secure Deployment Methods

#### Option 1: GitHub Actions with Secrets
```yaml
# .github/workflows/deploy.yml
- name: Deploy via SSH
  env:
    DEPLOY_KEY: ${{ secrets.DEPLOY_SSH_KEY }}
    DEPLOY_HOST: ${{ secrets.DEPLOY_HOST }}
  run: |
    # SSH deployment script
```

#### Option 2: CI/CD Pipeline
- Use GitLab CI, Jenkins, or CircleCI
- Store SSH keys in CI/CD secret management
- Never store keys in the repository

#### Option 3: Container Registry
- Push Docker images to registry
- Pull from registry on production server
- No direct SSH needed

### If SSH Is Required

Create a local (non-committed) SSH configuration:

```bash
# Create .ssh directory (gitignored)
mkdir -p .ssh
chmod 700 .ssh

# Create deployment key (DO NOT COMMIT)
ssh-keygen -t ed25519 -f .ssh/ghost_deploy_key -C "ghost-deploy"

# Create SSH config (DO NOT COMMIT)
cat > .ssh/config << EOF
Host ghost-prod
    HostName production.server.com
    User deploy
    Port 22
    IdentityFile ~/.ssh/ghost_deploy_key
    StrictHostKeyChecking yes
    PasswordAuthentication no
EOF

chmod 600 .ssh/config
```

## Port Forwarding Configuration

### Local Development
No port forwarding needed - all services on localhost.

### Production with Nginx
```nginx
# Port 443 (HTTPS) → localhost:8080 (API)
upstream ghost_backend {
    server 127.0.0.1:8080;
}

server {
    listen 443 ssl http2;
    location / {
        proxy_pass http://ghost_backend;
    }
}
```

### Docker Networking
```yaml
# docker-compose.yml
services:
  backend:
    ports:
      - "127.0.0.1:8888:8888"  # Host:Container
    environment:
      - DB_HOST=postgres        # Use service name
      - REDIS_HOST=redis        # Use service name
```

## Common Port Issues and Solutions

### Issue: Port Already in Use
```bash
# Check what's using a port
lsof -i :8000
# or
netstat -tulpn | grep 8000

# Kill process using port
kill -9 $(lsof -ti :8000)
```

### Issue: Connection Refused
1. Check service is running: `ps aux | grep python`
2. Verify binding address: Should be 127.0.0.1, not 0.0.0.0
3. Check firewall: `ufw status`

### Issue: Cannot Access from Browser
- Development: Use `localhost:8000` not `0.0.0.0:8000`
- Production: Access via domain name (HTTPS) not IP:port

## Environment-Specific Configurations

### Development (.env)
```env
API_HOST=127.0.0.1
API_PORT=8000
DEBUG=true
```

### Production (.env.production)
```env
API_HOST=127.0.0.1
API_PORT=8080
DEBUG=false
FORCE_HTTPS=true
```

### Docker (.env.docker)
```env
API_HOST=0.0.0.0  # Inside container
API_PORT=8888
DB_HOST=postgres  # Docker service name
REDIS_HOST=redis  # Docker service name
```

## Security Checklist

- [ ] All services bound to 127.0.0.1 in production
- [ ] Reverse proxy configured for external access
- [ ] Firewall rules implemented
- [ ] Database ports not exposed externally
- [ ] SSL/TLS certificates configured
- [ ] Rate limiting implemented
- [ ] Security headers configured
- [ ] No SSH keys in repository
- [ ] Environment-specific configurations separated
- [ ] Docker ports bound to localhost only

## Monitoring and Logging

### Port Monitoring
```bash
# Monitor open ports
watch -n 1 'netstat -tulpn | grep LISTEN'

# Check external accessibility
nmap -p 8000,8080,5432,6379 your-server.com
```

### Access Logs
- Nginx: `/var/log/nginx/access.log`
- API: `logs/ghost.log`
- Docker: `docker logs ghost-backend`

## Troubleshooting Commands

```bash
# Test API connectivity
curl -I http://127.0.0.1:8080/health

# Test from outside (should fail if properly configured)
curl -I http://your-server-ip:8080/health

# Check Docker network
docker network inspect ghost_default

# View Docker port mappings
docker ps --format "table {{.Names}}\t{{.Ports}}"

# Test database connectivity
psql -h 127.0.0.1 -U ghost -d ghost_db -c "SELECT 1"

# Test Redis connectivity
redis-cli -h 127.0.0.1 ping
```

## Important Notes

1. **Never expose database ports** to the internet
2. **Always use HTTPS** in production
3. **Implement rate limiting** to prevent abuse
4. **Use strong passwords** and rotate them regularly
5. **Monitor logs** for suspicious activity
6. **Keep services updated** with security patches
7. **Use SSH keys** instead of passwords for deployment
8. **Implement fail2ban** for brute force protection

## References

- [OWASP Security Guidelines](https://owasp.org/)
- [nginx Security Best Practices](https://docs.nginx.com/nginx/admin-guide/security-controls/)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [PostgreSQL Security](https://www.postgresql.org/docs/current/security.html)