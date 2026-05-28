#!/bin/bash

# Deployment Script for Trading System with MCP Agent
# Usage: ./deploy.sh [environment]
# Environments: local, docker, heroku, aws

set -e

ENVIRONMENT=${1:-local}
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  TRADING SYSTEM DEPLOYMENT SCRIPT                          ║"
echo "║  Environment: $ENVIRONMENT"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
print_step() {
    echo -e "${YELLOW}→${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Define deployment functions first (before they're called)

deploy_local() {
    echo ""
    print_step "LOCAL DEPLOYMENT"
    print_step "=================="
    echo ""

    print_step "Installing dependencies..."
    pip install -q -r "$PROJECT_DIR/requirements_phase3b.txt"
    pip install -q aiohttp
    print_success "Dependencies installed"

    print_step "Backing up old app.py..."
    if [ -f "$PROJECT_DIR/app.py" ]; then
        cp "$PROJECT_DIR/app.py" "$PROJECT_DIR/app_backup_$(date +%s).py"
        print_success "Backup created"
    fi

    print_step "Installing integrated app..."
    cp "$PROJECT_DIR/app_integrated.py" "$PROJECT_DIR/app.py"
    print_success "App.py updated"

    print_step "Verifying imports..."
    python3 -c "
from mcp_stock_agent import MCPStockAgent
from notification_manager import NotificationManager
print('✓ All imports successful')
" || exit 1

    print_success "Local deployment ready"
    echo ""
    echo "To start the server, run:"
    echo "  python3 app.py"
    echo ""
    echo "Or with development reload:"
    echo "  uvicorn app:app --reload --host 0.0.0.0 --port 8000"
    echo ""
}

deploy_docker() {
    echo ""
    print_step "DOCKER DEPLOYMENT"
    print_step "=================="
    echo ""

    if ! command -v docker &> /dev/null; then
        print_error "Docker not found. Install Docker first."
        exit 1
    fi
    print_success "Docker found"

    print_step "Building Docker image..."
    docker build -t trading-system:3.1.0 "$PROJECT_DIR"
    print_success "Docker image built"

    print_step "Starting Docker Compose..."
    docker-compose -f "$PROJECT_DIR/docker-compose.yml" up -d
    print_success "Docker services started"

    print_step "Waiting for services to be healthy..."
    sleep 10

    print_step "Checking health..."
    if curl -s http://localhost:8000/health > /dev/null; then
        print_success "API is healthy"
    else
        print_error "API health check failed"
        docker-compose -f "$PROJECT_DIR/docker-compose.yml" logs api
        exit 1
    fi

    echo ""
    echo "Services running:"
    docker-compose -f "$PROJECT_DIR/docker-compose.yml" ps
    echo ""
    echo "To view logs:"
    echo "  docker-compose logs -f api"
    echo ""
    echo "To stop:"
    echo "  docker-compose down"
    echo ""
}

deploy_heroku() {
    echo ""
    print_step "HEROKU DEPLOYMENT"
    print_step "=================="
    echo ""

    if ! command -v heroku &> /dev/null; then
        print_error "Heroku CLI not found. Install it first:"
        echo "  https://devcenter.heroku.com/articles/heroku-cli"
        exit 1
    fi
    print_success "Heroku CLI found"

    print_step "Checking Heroku authentication..."
    if ! heroku auth:whoami > /dev/null 2>&1; then
        print_error "Not logged in to Heroku"
        echo "Run: heroku login"
        exit 1
    fi
    print_success "Authenticated with Heroku"

    print_step "Creating Procfile..."
    cat > "$PROJECT_DIR/Procfile" << 'EOF'
web: uvicorn app:app --host=0.0.0.0 --port=${PORT:-8000} --workers 2
EOF
    print_success "Procfile created"

    print_step "Committing changes..."
    cd "$PROJECT_DIR"
    git add -A
    git commit -m "Integrate MCP agent - ready for Heroku deployment" || true

    print_step "Pushing to Heroku..."
    git push heroku main

    print_success "App deployed to Heroku"
    echo ""
    echo "Next steps:"
    echo "  1. Set environment variables:"
    echo "     heroku config:set SLACK_WEBHOOK_URL=YOUR_WEBHOOK"
    echo "     heroku config:set EMAIL_USER=YOUR_EMAIL"
    echo "     heroku config:set EMAIL_PASSWORD=YOUR_PASSWORD"
    echo ""
    echo "  2. View logs:"
    echo "     heroku logs --tail"
    echo ""
    echo "  3. Open app:"
    echo "     heroku open"
    echo ""
}

deploy_aws() {
    echo ""
    print_step "AWS DEPLOYMENT"
    print_step "=================="
    echo ""
    print_error "AWS deployment requires manual setup"
    echo ""
    echo "See DEPLOYMENT_GUIDE.md for AWS EC2/ECS setup instructions"
    echo ""
    echo "Quick summary:"
    echo "  1. Launch EC2 instance"
    echo "  2. Install Docker"
    echo "  3. Clone repository"
    echo "  4. Configure .env"
    echo "  5. Run: docker-compose -f docker-compose.prod.yml up -d"
    echo ""
}

# Main script execution starts here
echo ""
print_step "Running pre-flight checks..."

if ! command -v python3 &> /dev/null; then
    print_error "Python 3 not found"
    exit 1
fi
print_success "Python 3 found"

if ! command -v git &> /dev/null; then
    print_error "Git not found"
    exit 1
fi
print_success "Git found"

# Check required files
required_files=("app_integrated.py" "mcp_stock_agent.py" "notification_manager.py" ".env.example")
for file in "${required_files[@]}"; do
    if [ ! -f "$PROJECT_DIR/$file" ]; then
        print_error "Required file not found: $file"
        exit 1
    fi
done
print_success "All required files present"

echo ""
print_step "Preparing environment..."

# Create .env if it doesn't exist
if [ ! -f "$PROJECT_DIR/.env" ]; then
    print_step "Creating .env from .env.example..."
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    print_success ".env created (update with your values)"
else
    print_success ".env already exists"
fi

# Create logs directory
mkdir -p "$PROJECT_DIR/logs"
print_success "Logs directory ready"

echo ""
print_step "Deploying to: $ENVIRONMENT"

case $ENVIRONMENT in
    local)
        deploy_local
        ;;
    docker)
        deploy_docker
        ;;
    heroku)
        deploy_heroku
        ;;
    aws)
        deploy_aws
        ;;
    *)
        print_error "Unknown environment: $ENVIRONMENT"
        echo "Usage: $0 [local|docker|heroku|aws]"
        exit 1
        ;;
esac

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  DEPLOYMENT COMPLETE                                       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
print_success "System deployed successfully!"
echo ""
echo "Next steps:"
echo "  1. Verify installation: curl http://localhost:8000/health"
echo "  2. Check agent status: curl -H 'Authorization: Bearer test-token' http://localhost:8000/api/v1/agent/status"
echo "  3. View API docs: http://localhost:8000/api/docs"
echo "  4. Review logs: tail -f logs/trading-system.log"
echo ""
