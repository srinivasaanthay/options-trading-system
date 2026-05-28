# Deployment Guide

Complete guide for deploying the Options Trading System to various platforms.

---

## Table of Contents

1. [Local Deployment (Docker)](#local-deployment-docker)
2. [Heroku Deployment](#heroku-deployment)
3. [AWS Deployment](#aws-deployment)
4. [Azure Deployment](#azure-deployment)
5. [DigitalOcean Deployment](#digitalocean-deployment)
6. [Self-Hosted Deployment](#self-hosted-deployment)

---

## Local Deployment (Docker)

### Prerequisites
- Docker installed
- Docker Compose installed
- 4GB RAM minimum

### Quick Start

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/options-trading-system.git
cd options-trading-system

# Start services
docker-compose up -d

# Wait for services to be healthy
docker-compose ps

# Test API
curl http://localhost:8000/health

# View logs
docker-compose logs -f api
```

### Access Points
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/docs
- **Database**: localhost:5432 (postgres/postgres)
- **Redis**: localhost:6379
- **pgAdmin**: http://localhost:5050 (admin@example.com/admin) - if `--profile admin` used

### Stop Services

```bash
docker-compose down
```

---

## Heroku Deployment

### Prerequisites
- Heroku CLI installed
- Heroku account (free or paid)
- GitHub account

### Step 1: Create Heroku App

```bash
# Login to Heroku
heroku login

# Create app
heroku create your-app-name

# Create Procfile
cat > Procfile << 'EOF'
web: uvicorn app:app --host=0.0.0.0 --port=${PORT:-8000}
EOF

# Add Procfile to git
git add Procfile
git commit -m "Add Heroku Procfile"
```

### Step 2: Configure Environment

```bash
# Set environment variables
heroku config:set LOG_LEVEL=INFO
heroku config:set SECRET_KEY=your-secret-key-here
heroku config:set DATABASE_URL=postgresql://...

# View configuration
heroku config
```

### Step 3: Add Postgres (Optional)

```bash
# Add PostgreSQL add-on
heroku addons:create heroku-postgresql:hobby-dev

# Database URL is set automatically in DATABASE_URL
heroku config | grep DATABASE_URL
```

### Step 4: Deploy

```bash
# Deploy using Git
git push heroku main

# Or link GitHub for automatic deployments
heroku apps:set remote heroku-app-name
heroku plugins:install @heroku-cli/plugin-github-ci
heroku github:repo:connect
heroku pipelines:create trading-system-pipeline
```

### Step 5: Monitor

```bash
# View logs
heroku logs --tail

# Check dyno status
heroku ps

# Run commands
heroku run python -c "from analyzer.news_analyzer import NewsAnalyzer; NewsAnalyzer()"
```

### Scaling

```bash
# Scale web dynos
heroku ps:scale web=2

# View costs
heroku billing:what-it-will-cost
```

---

## AWS Deployment

### Option A: EC2 + Docker

#### Prerequisites
- AWS account
- EC2 instance (t3.medium or larger)
- Security group allowing ports 80, 443, 8000

#### Deployment Steps

```bash
# SSH into EC2 instance
ssh -i your-key.pem ec2-user@your-instance.com

# Install Docker and Docker Compose
sudo amazon-linux-extras install docker
sudo usermod -a -G docker ec2-user
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Clone repository
git clone https://github.com/YOUR_USERNAME/options-trading-system.git
cd options-trading-system

# Create .env file
cat > .env << 'EOF'
DATABASE_URL=postgresql://postgres:password@db:5432/trading_db
REDIS_URL=redis://redis:6379/0
SECRET_KEY=your-secret-key
LOG_LEVEL=INFO
EOF

# Start services
docker-compose up -d

# Setup reverse proxy with nginx
sudo yum install nginx
# Configure nginx (see nginx.conf below)
```

#### nginx.conf

```nginx
upstream api {
    server localhost:8000;
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Option B: ECS + Fargate

```bash
# 1. Build and push Docker image to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789.dkr.ecr.us-east-1.amazonaws.com
docker build -t options-trading-system .
docker tag options-trading-system:latest 123456789.dkr.ecr.us-east-1.amazonaws.com/options-trading-system:latest
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/options-trading-system:latest

# 2. Create ECS cluster
aws ecs create-cluster --cluster-name trading-system

# 3. Create task definition
# (See ecs-task-definition.json below)

# 4. Create service
aws ecs create-service --cluster trading-system --service-name api --task-definition options-trading-system --desired-count 2 --launch-type FARGATE
```

#### ecs-task-definition.json

```json
{
  "family": "options-trading-system",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [
    {
      "name": "api",
      "image": "123456789.dkr.ecr.us-east-1.amazonaws.com/options-trading-system:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "LOG_LEVEL",
          "value": "INFO"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/options-trading-system",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

---

## Azure Deployment

### Option A: App Service + Docker

```bash
# Login to Azure
az login

# Create resource group
az group create --name trading-rg --location eastus

# Create App Service plan
az appservice plan create --name trading-plan --resource-group trading-rg --sku B1 --is-linux

# Create Web App
az webapp create --resource-group trading-rg --plan trading-plan --name options-trading-api --deployment-container-image-name trading-system

# Configure container settings
az webapp config container set --name options-trading-api --resource-group trading-rg \
  --docker-custom-image-name your-registry.azurecr.io/options-trading-system:latest \
  --docker-registry-server-url https://your-registry.azurecr.io \
  --docker-registry-server-user <username> \
  --docker-registry-server-password <password>

# Set environment variables
az webapp config appsettings set --resource-group trading-rg --name options-trading-api \
  --settings DATABASE_URL="postgresql://..." LOG_LEVEL="INFO"
```

### Option B: Container Instances

```bash
# Create container group
az container create --resource-group trading-rg \
  --name options-trading-container \
  --image trading-system:latest \
  --cpu 1 --memory 1 \
  --port 8000 \
  --environment-variables LOG_LEVEL=INFO \
  --registry-login-server your-registry.azurecr.io \
  --registry-username <username> \
  --registry-password <password>
```

---

## DigitalOcean Deployment

### Option A: App Platform

```bash
# Create app.yaml
cat > app.yaml << 'EOF'
name: options-trading-system
services:
- name: api
  github:
    branch: main
    repo: YOUR_USERNAME/options-trading-system
  build_command: pip install -r requirements_phase3b.txt
  run_command: uvicorn app:app --host 0.0.0.0
  http_port: 8000
  envs:
  - key: LOG_LEVEL
    value: INFO
  - key: DATABASE_URL
    value: ${db.connection_string}

databases:
- name: db
  engine: PG
  version: "13"
EOF

# Deploy
doctl apps create --spec app.yaml
```

### Option B: Droplet + Docker

```bash
# Create droplet
doctl compute droplet create options-trading-api \
  --region nyc1 \
  --image docker-20-10-21-ow \
  --size s-1vcpu-1gb

# SSH into droplet
ssh root@your-droplet-ip

# Clone and deploy
git clone https://github.com/YOUR_USERNAME/options-trading-system.git
cd options-trading-system
docker-compose up -d
```

---

## Self-Hosted Deployment

### Prerequisites
- Linux server (Ubuntu 20.04+ recommended)
- 4GB RAM minimum
- 20GB disk space
- Domain name (optional but recommended)

### Installation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Clone repository
git clone https://github.com/YOUR_USERNAME/options-trading-system.git
cd options-trading-system

# Create environment file
cp .env.example .env
# Edit .env with production values
nano .env

# Start services
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose ps
```

### SSL with Let's Encrypt

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot certonly --standalone -d your-domain.com

# Configure auto-renewal
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

### Monitoring

```bash
# Install Prometheus + Grafana (optional)
docker-compose -f docker-compose.monitoring.yml up -d

# View metrics
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000
```

---

## Production Checklist

- [ ] Set strong `SECRET_KEY`
- [ ] Configure `DATABASE_URL` with secure credentials
- [ ] Enable HTTPS/SSL
- [ ] Set `LOG_LEVEL=WARNING` for production
- [ ] Configure database backups
- [ ] Set up monitoring and alerts
- [ ] Configure auto-scaling (if using cloud)
- [ ] Review security group/firewall rules
- [ ] Enable rate limiting
- [ ] Set up log aggregation
- [ ] Test disaster recovery procedures
- [ ] Document deployment process
- [ ] Plan for maintenance windows

---

## Monitoring & Debugging

### View Logs

**Docker:**
```bash
docker-compose logs -f api
docker-compose logs --tail=100 api
```

**Heroku:**
```bash
heroku logs --tail
```

**AWS CloudWatch:**
```bash
aws logs tail /ecs/options-trading-system --follow
```

### Performance Monitoring

```bash
# Inside container
docker-compose exec api python -m cProfile -s cumtime app.py

# Or use APM tool
# New Relic, Datadog, Splunk, etc.
```

### Debugging

```bash
# Shell into running container
docker-compose exec api sh

# Check health
curl http://localhost:8000/health

# Test database connection
docker-compose exec api python -c "import sqlalchemy; print('DB OK')"
```

---

## Disaster Recovery

### Backup Database

```bash
# Automated daily backups
docker-compose exec db pg_dump -U postgres trading_db > backup_$(date +%Y%m%d).sql

# Or configure automated backups in cloud provider
```

### Restore from Backup

```bash
# Restore PostgreSQL
cat backup_20240101.sql | docker-compose exec -T db psql -U postgres trading_db
```

---

## Cost Optimization

### Local/Self-Hosted
- Free (except infrastructure)

### Heroku
- **Free**: Limited (sleep after 30 min inactivity)
- **Hobby**: $7/month per dyno
- **Standard**: $50+/month per dyno

### AWS
- **EC2 t3.medium**: ~$35/month
- **RDS t3.micro**: ~$15/month
- **Free tier**: First year free

### Azure
- **App Service B1**: ~$55/month
- **Database**: ~$15/month

### DigitalOcean
- **Droplet**: $6-24/month
- **App Platform**: $12+/month
- **Database**: $15/month

---

## Conclusion

The Options Trading System can be deployed on various platforms. Choose based on:
- Budget
- Expected scale
- Maintenance preference
- Geographic requirements

For getting started, **Docker (local)** or **Heroku** are recommended.

---

**Last Updated**: May 2026  
**Version**: 3.0.0
