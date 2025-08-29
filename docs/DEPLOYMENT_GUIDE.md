# ============================================================================
# DEPLOYMENT CONFIGURATION GUIDE - Ghost Backend Framework
# ============================================================================

## 🐳 Docker Deployment

### 1. Create Dockerfile
```dockerfile
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY pyproject.toml ./

# Install the application
RUN pip install -e .

# Create non-root user
RUN useradd --create-home --shell /bin/bash ghost
RUN chown -R ghost:ghost /app
USER ghost

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "src.ghost.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2. Docker Compose Configuration
```yaml
version: '3.8'

services:
  # Main application
  ghost-backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/ghost_db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis
    volumes:
      - ./logs:/app/logs
      - ./uploads:/app/uploads
    restart: unless-stopped
    networks:
      - ghost-network

  # PostgreSQL Database
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: ghost_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    restart: unless-stopped
    networks:
      - ghost-network

  # Redis Cache
  redis:
    image: redis:7-alpine
    command: redis-server --requirepass password
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    networks:
      - ghost-network

  # Nginx Reverse Proxy
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - ghost-backend
    restart: unless-stopped
    networks:
      - ghost-network

volumes:
  postgres_data:
  redis_data:

networks:
  ghost-network:
    driver: bridge
```

### 3. Nginx Configuration
```nginx
events {
    worker_connections 1024;
}

http {
    upstream ghost_backend {
        server ghost-backend:8000;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

    server {
        listen 80;
        server_name yourdomain.com www.yourdomain.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name yourdomain.com www.yourdomain.com;

        # SSL Configuration
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384;

        # Security headers
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";

        # API endpoints
        location /api/ {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://ghost_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Health check (no rate limiting)
        location /health {
            proxy_pass http://ghost_backend;
            proxy_set_header Host $host;
        }

        # Static files
        location /static/ {
            alias /app/static/;
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }
}
```

## ☁️ Cloud Platform Deployments

### AWS Deployment

#### 1. EC2 with Docker
```bash
#!/bin/bash
# User data script for EC2 instance

# Update system
yum update -y

# Install Docker
amazon-linux-extras install docker -y
systemctl start docker
systemctl enable docker
usermod -a -G docker ec2-user

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/download/v2.21.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Clone your application
git clone https://github.com/your-repo/ghost-backend.git /app
cd /app

# Set up environment
cp .env.production.example .env
# Edit .env with your production values

# Start services
docker-compose up -d
```

#### 2. ECS (Elastic Container Service)
```json
{
  "family": "ghost-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::123456789:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "ghost-backend",
      "image": "your-account.dkr.ecr.region.amazonaws.com/ghost-backend:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "ENVIRONMENT", "value": "production"},
        {"name": "DATABASE_URL", "value": "postgresql://user:pass@rds-endpoint:5432/db"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/ghost-backend",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

#### 3. Lambda Deployment (Serverless)
```yaml
# serverless.yml
service: ghost-backend

provider:
  name: aws
  runtime: python3.9
  region: us-east-1
  environment:
    DATABASE_URL: ${env:DATABASE_URL}
    JWT_SECRET_KEY: ${env:JWT_SECRET_KEY}

functions:
  api:
    handler: src.ghost.lambda_handler.handler
    events:
      - http:
          path: /{proxy+}
          method: ANY
          cors: true
    timeout: 30
    memorySize: 512

plugins:
  - serverless-python-requirements
  - serverless-wsgi

custom:
  wsgi:
    app: src.ghost.api.app
  pythonRequirements:
    dockerizePip: true
```

### Google Cloud Platform (GCP)

#### 1. Cloud Run Deployment
```yaml
# cloudbuild.yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/ghost-backend', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/ghost-backend']
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: 'gcloud'
    args:
      - 'run'
      - 'deploy'
      - 'ghost-backend'
      - '--image'
      - 'gcr.io/$PROJECT_ID/ghost-backend'
      - '--region'
      - 'us-central1'
      - '--platform'
      - 'managed'
```

#### 2. App Engine Deployment
```yaml
# app.yaml
runtime: python39

env_variables:
  ENVIRONMENT: production
  DATABASE_URL: postgresql://user:pass@/dbname?host=/cloudsql/project:region:instance
  JWT_SECRET_KEY: your-secret-key

automatic_scaling:
  min_instances: 1
  max_instances: 10

resources:
  cpu: 1
  memory_gb: 2
  disk_size_gb: 10
```

### Microsoft Azure

#### 1. Container Instances
```json
{
  "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "containerName": {
      "type": "string",
      "defaultValue": "ghost-backend"
    }
  },
  "resources": [
    {
      "type": "Microsoft.ContainerInstance/containerGroups",
      "apiVersion": "2019-12-01",
      "name": "[parameters('containerName')]",
      "location": "[resourceGroup().location]",
      "properties": {
        "containers": [
          {
            "name": "ghost-backend",
            "properties": {
              "image": "your-registry.azurecr.io/ghost-backend:latest",
              "ports": [{"port": 8000}],
              "environmentVariables": [
                {"name": "ENVIRONMENT", "value": "production"},
                {"name": "DATABASE_URL", "secureValue": "[parameters('databaseUrl')]"}
              ],
              "resources": {
                "requests": {"cpu": 1, "memoryInGb": 1}
              }
            }
          }
        ],
        "osType": "Linux",
        "ipAddress": {
          "type": "Public",
          "ports": [{"protocol": "TCP", "port": 8000}]
        }
      }
    }
  ]
}
```

## 🔄 CI/CD Pipeline Configuration

### GitHub Actions
```yaml
# .github/workflows/deploy.yml
name: Deploy Ghost Backend

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
      
      - name: Run tests
        run: |
          pytest --cov=src/ghost --cov-report=xml
      
      - name: Code quality checks
        run: |
          black --check src/
          isort --check-only src/
          flake8 src/
          mypy src/

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      
      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v1
      
      - name: Build and push Docker image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          ECR_REPOSITORY: ghost-backend
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
      
      - name: Deploy to ECS
        run: |
          # Update ECS service with new image
          aws ecs update-service --cluster ghost-cluster --service ghost-backend --force-new-deployment
```

### GitLab CI/CD
```yaml
# .gitlab-ci.yml
stages:
  - test
  - build
  - deploy

variables:
  DOCKER_IMAGE: $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA

test:
  stage: test
  image: python:3.13
  script:
    - pip install -e ".[dev]"
    - pytest --cov=src/ghost
    - black --check src/
    - flake8 src/
    - mypy src/

build:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  script:
    - docker build -t $DOCKER_IMAGE .
    - docker push $DOCKER_IMAGE
  only:
    - main

deploy:
  stage: deploy
  script:
    - kubectl set image deployment/ghost-backend ghost-backend=$DOCKER_IMAGE
    - kubectl rollout status deployment/ghost-backend
  only:
    - main
```

## 📊 Monitoring and Observability

### 1. Application Performance Monitoring
```env
# Sentry for error tracking
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1

# Prometheus metrics
METRICS_ENABLED=true
METRICS_PORT=9090

# Health checks
HEALTH_CHECK_INTERVAL=30
HEALTH_CHECK_TIMEOUT=10
```

### 2. Logging Configuration
```env
# Structured logging for production
LOG_FORMAT=json
LOG_LEVEL=INFO

# Log aggregation
LOG_AGGREGATION_ENABLED=true
ELASTICSEARCH_URL=https://elasticsearch.example.com:9200
KIBANA_URL=https://kibana.example.com:5601

# Log retention
LOG_RETENTION_DAYS=30
LOG_ROTATION=daily
```

### 3. Database Monitoring
```python
# Example monitoring setup
from ghost import DatabaseManager
import asyncio

async def monitor_database():
    db_manager = DatabaseManager(config.database)
    
    while True:
        # Check connection pool status
        pool_status = await db_manager.get_pool_status()
        
        # Log metrics
        logger.info("Database metrics", extra={
            "active_connections": pool_status.active,
            "idle_connections": pool_status.idle,
            "pool_size": pool_status.size
        })
        
        await asyncio.sleep(60)  # Check every minute
```

## 🔧 Environment-Specific Configurations

### Development Environment
```env
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
API_CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
DATABASE_URL=sqlite:///./dev.db
REDIS_URL=redis://localhost:6379/0
```

### Staging Environment
```env
ENVIRONMENT=staging
DEBUG=false
LOG_LEVEL=INFO
DATABASE_URL=postgresql://user:pass@staging-db.example.com:5432/ghost_staging
REDIS_URL=redis://staging-redis.example.com:6379/0
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
```

### Production Environment
```env
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=WARNING
FORCE_HTTPS=true
DATABASE_URL=postgresql://user:pass@prod-db.example.com:5432/ghost_prod?sslmode=require
REDIS_URL=redis://prod-redis.example.com:6379/0
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
SENTRY_DSN=https://your-production-sentry-dsn@sentry.io/project
```

## 🚀 Scaling Considerations

### 1. Horizontal Scaling
```yaml
# Kubernetes horizontal pod autoscaler
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ghost-backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ghost-backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### 2. Database Scaling
```env
# Read replicas
DATABASE_REPLICA_URLS=postgresql://user:pass@replica1.example.com:5432/ghost_prod,postgresql://user:pass@replica2.example.com:5432/ghost_prod

# Connection pooling
DB_POOL_SIZE=50
DB_MAX_OVERFLOW=100
DB_POOL_TIMEOUT=30
```

### 3. Caching Strategy
```env
# Redis clustering
REDIS_CLUSTER_ENABLED=true
REDIS_CLUSTER_NODES=redis1.example.com:6379,redis2.example.com:6379,redis3.example.com:6379

# Cache TTL settings
CACHE_DEFAULT_TTL=300
CACHE_LONG_TTL=3600
CACHE_SHORT_TTL=60
```

Remember to test your deployment configuration thoroughly before going to production!
