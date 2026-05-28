# CI/CD Setup & Deployment Guide

## Overview

This project includes a comprehensive CI/CD pipeline using GitHub Actions with automated testing, code quality checks, and deployment workflows.

---

## GitHub Actions Workflows

### 1. Tests Workflow (`.github/workflows/tests.yml`)

**Trigger**: On push to main/develop, or pull request  
**Purpose**: Automated testing and coverage reporting

**What it does:**
- Runs tests on Python 3.9, 3.10, and 3.11
- Installs dependencies
- Runs linting with flake8
- Performs type checking with mypy
- Executes 277 unit tests
- Generates coverage reports
- Uploads coverage to Codecov
- Tests analyzer initialization
- Verifies FastAPI backend imports

**Key outputs:**
- Test results artifact
- Coverage reports (HTML)
- Coverage badge for README

**View status**: Go to Actions tab on GitHub

### 2. Code Quality Workflow (`.github/workflows/code-quality.yml`)

**Trigger**: On push to main/develop, or pull request  
**Purpose**: Code quality and security checks

**What it does:**
- Checks code formatting (black)
- Verifies import sorting (isort)
- Lints code (flake8)
- Security scanning (bandit)
- Type checking (mypy)
- Dependency vulnerability scanning (pip-audit, safety)

**Key outputs:**
- Quality reports artifact
- Security vulnerability list

### 3. Deploy Workflow (`.github/workflows/deploy.yml`)

**Trigger**: On push to main (production deployment)  
**Purpose**: Automated deployment to production

**What it does:**
- Checks out code
- Installs dependencies
- Runs all tests
- Builds Docker image
- Creates deployment artifact
- Generates GitHub release
- Notifies deployment status

**Key outputs:**
- Docker image
- Deployment ZIP artifact
- GitHub Release

---

## Docker Setup

### Dockerfile (Multi-stage build)

**Stages:**
1. **Builder**: Compiles Python wheels
2. **Runtime**: Minimal runtime environment

**Features:**
- Multi-stage build for smaller image size
- Non-root user (appuser) for security
- Health check endpoint
- Environment variables pre-configured
- Minimal dependencies

**Build:**
```bash
docker build -t options-trading-system:latest .
```

**Run:**
```bash
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:pass@db:5432/db \
  options-trading-system:latest
```

### Docker Compose

**Services:**
1. **api** - FastAPI application
2. **db** - PostgreSQL database
3. **redis** - Redis cache
4. **celery-worker** - Task processing (optional)
5. **celery-beat** - Task scheduling (optional)
6. **pgadmin** - Database UI (optional)

**Basic start:**
```bash
docker-compose up -d
```

**Start with Celery:**
```bash
docker-compose --profile celery up -d
```

**Start with admin tools:**
```bash
docker-compose --profile admin up -d
```

**View logs:**
```bash
docker-compose logs -f api
```

**Stop everything:**
```bash
docker-compose down
```

---

## Setting Up CI/CD

### Step 1: Push Code to GitHub

Your code should already be pushed. Verify at:
```
https://github.com/YOUR_USERNAME/options-trading-system
```

### Step 2: Enable GitHub Actions

1. Go to your repository
2. Click "Actions" tab
3. Click "I understand my workflows, go ahead and enable them"
4. Workflows should now run automatically on push

### Step 3: Configure Secrets (Optional)

For production deployment, add these secrets:

1. Go to Settings → Secrets → Actions
2. Click "New repository secret"
3. Add secrets:

**Required for deployment:**
- `DEPLOY_KEY` - SSH key for deployment
- `DOCKER_USERNAME` - Docker Hub username
- `DOCKER_PASSWORD` - Docker Hub token
- `DATABASE_URL` - Production database URL

**Optional:**
- `SLACK_WEBHOOK` - For Slack notifications
- `SENDGRID_API_KEY` - For email notifications

### Step 4: View Workflow Status

1. Push code to GitHub
2. Go to Actions tab
3. Watch workflows run:
   - Tests (5-10 minutes)
   - Code Quality (2-3 minutes)
   - Deploy (if on main branch)

---

## Local Development with Docker

### Start Development Environment

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Run tests inside container
docker-compose exec api pytest analyzer/ -v

# Access API
curl http://localhost:8000/health

# Access database
docker-compose exec db psql -U postgres -d trading_db

# Access Redis
docker-compose exec redis redis-cli
```

### Stop Development Environment

```bash
docker-compose down

# Remove volumes too (careful - deletes data)
docker-compose down -v
```

### Debug Issues

```bash
# View service logs
docker-compose logs api

# Check service health
docker-compose ps

# Rebuild specific service
docker-compose build --no-cache api

# Remove and recreate
docker-compose down
docker-compose up -d
```

---

## CI/CD Pipeline Stages

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Push Event                         │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┴────────────────┐
         │                                │
    ┌────▼──────┐              ┌─────────▼──────────┐
    │   Tests   │              │  Code Quality      │
    └────┬──────┘              └─────────┬──────────┘
         │                               │
    [Run tests]                    [Check formatting]
    [Coverage]                     [Lint code]
    [Validate]                     [Security scan]
         │                               │
         └───────────────┬───────────────┘
                         │
          ┌──────────────▼──────────────┐
          │  All Checks Pass? (if main) │
          └──────────────┬──────────────┘
                         │
              ┌──────────▼──────────┐
              │    Deploy Stage     │
              │  (if on main only)  │
              └──────────┬──────────┘
                         │
    ┌────────────────────┼────────────────────┐
    │                    │                    │
┌───▼────┐        ┌──────▼──────┐      ┌─────▼──────┐
│ Build  │        │ Create      │      │   Test     │
│ Docker │        │ Release     │      │  Deploy    │
└────────┘        └─────────────┘      └────────────┘
```

---

## Common Tasks

### Check Test Status

```bash
# GitHub Actions UI
https://github.com/YOUR_USERNAME/options-trading-system/actions

# Command line (requires GitHub CLI)
gh run list
gh run view <run-id>
```

### Re-run Failed Workflow

1. Go to Actions tab
2. Click the failed workflow
3. Click "Re-run jobs"

### View Coverage Report

1. Go to latest successful Tests workflow
2. Click "Artifacts"
3. Download coverage report
4. Open `htmlcov/index.html`

### Deploy Manually

1. Go to Actions → Deploy
2. Click "Run workflow"
3. Select branch
4. Click "Run workflow"

### Build Docker Image Locally

```bash
# Build
docker build -t trading-system:local .

# Run
docker run -p 8000:8000 trading-system:local

# Push to Docker Hub
docker tag trading-system:local USERNAME/trading-system:latest
docker push USERNAME/trading-system:latest
```

---

## Monitoring & Alerts

### GitHub Status Checks

- All workflows must pass to merge PRs
- Status shown on PR page
- Checks required: Tests, Code Quality

### Coverage Tracking

- Coverage badge in README (if using Codecov)
- Coverage trends on Codecov.io dashboard
- Set minimum coverage threshold (default: 70%)

### Deployment Notifications

**Current**: Console logs in GitHub Actions

**Optional additions**:
- Slack notifications (webhook)
- Email notifications (SendGrid)
- PagerDuty alerts (critical failures)

---

## Troubleshooting

### Tests Fail Locally but Pass in CI

```bash
# Ensure same Python version as CI
python --version  # Should be 3.10

# Install exact requirements
pip install -r requirements_phase3b.txt

# Run tests same way as CI
pytest analyzer/ -v --tb=short
```

### Docker Build Fails

```bash
# Clear Docker cache
docker system prune

# Rebuild without cache
docker build --no-cache -t trading-system .

# Check Dockerfile syntax
docker build --progress=plain .
```

### Docker Compose Issues

```bash
# View detailed logs
docker-compose logs --tail=100

# Check service health
docker-compose ps

# Verify network
docker network inspect trading_network

# Rebuild services
docker-compose down && docker-compose up -d
```

### Workflow Stuck

1. Check GitHub Status: https://www.githubstatus.com/
2. Cancel workflow: Actions → Click running workflow → Cancel
3. Check for secrets missing (see Settings → Secrets)
4. Verify branch protection rules (Settings → Branches)

---

## Security Best Practices

1. **Secrets Management**
   - Never commit secrets
   - Use GitHub Secrets for sensitive data
   - Rotate keys regularly

2. **Access Control**
   - Limit deployment permissions
   - Require code review for main branch
   - Use branch protection rules

3. **Dependency Security**
   - Dependabot automatically scans dependencies
   - Review and apply security updates
   - Use pinned versions in production

4. **Container Security**
   - Non-root user in Dockerfile
   - Minimal base image (python:3.10-slim)
   - No hardcoded secrets in image
   - Scan image for vulnerabilities

---

## Performance Optimization

### Faster CI/CD

1. **Caching**
   - Pip cache is already configured
   - Docker layer caching

2. **Parallel Jobs**
   - Tests run on 3 Python versions in parallel
   - Code quality checks run separately

3. **Docker Layer Caching**
   - Build stages minimize rebuilds
   - Wheels cached in builder stage

4. **Skip Rules**
   - Add `[skip ci]` to commit message to skip workflows

---

## Next Steps

1. **Push CI/CD Files to GitHub**
   ```bash
   git add .github/ Dockerfile docker-compose.yml CI_CD_SETUP.md
   git commit -m "Add CI/CD pipeline and Docker configuration"
   git push origin main
   ```

2. **Watch First Workflow Run**
   - Go to Actions tab
   - Verify all checks pass

3. **Configure Branch Protection** (Optional)
   - Settings → Branches → Add rule
   - Require status checks to pass before merging

4. **Set Up Monitoring** (Optional)
   - Configure Slack notifications
   - Add code coverage badge to README

5. **Continue Phase 3B**
   - Implement database models
   - Add authentication
   - Build data persistence

---

## Additional Resources

- GitHub Actions Docs: https://docs.github.com/en/actions
- Docker Docs: https://docs.docker.com/
- Docker Compose: https://docs.docker.com/compose/
- Pytest: https://pytest.org/
- FastAPI: https://fastapi.tiangolo.com/
- PostgreSQL: https://www.postgresql.org/docs/

---

**CI/CD Setup Complete!** 🚀

Your project now has:
- ✅ Automated testing on every push
- ✅ Code quality checks
- ✅ Automated deployment
- ✅ Docker containerization
- ✅ Local development environment
