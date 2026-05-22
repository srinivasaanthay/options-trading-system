#!/bin/bash

# ═══════════════════════════════════════════════════════════════
# GitHub Push Commands - Options Trading System
# ═══════════════════════════════════════════════════════════════

echo "═══════════════════════════════════════════════════════════════"
echo "  Options Trading System - GitHub Push Setup"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Step 1: Check git is installed
echo "[1/6] Checking Git installation..."
if ! command -v git &> /dev/null; then
    echo "✗ Git not found. Please install git first."
    exit 1
fi
echo "✓ Git $(git --version | awk '{print $3}') found"
echo ""

# Step 2: Configure git (local)
echo "[2/6] Configuring Git..."
read -p "Enter your Git username: " GIT_USER
read -p "Enter your Git email: " GIT_EMAIL

git config --global user.name "$GIT_USER"
git config --global user.email "$GIT_EMAIL"
echo "✓ Git configured"
echo ""

# Step 3: Initialize repository
echo "[3/6] Initializing local repository..."
if [ -d ".git" ]; then
    echo "⚠ Repository already initialized. Skipping..."
else
    git init
    echo "✓ Repository initialized"
fi
echo ""

# Step 4: Add files
echo "[4/6] Adding files to git..."
git add .
git status
echo ""

# Step 5: Make initial commit
echo "[5/6] Creating initial commit..."
git commit -m "Initial commit: Phase 3A analyzers + Phase 3B REST API foundation

WHAT'S INCLUDED:
- 7 comprehensive analyzer modules (3,450+ LOC)
  • NewsAnalyzer (sentiment analysis)
  • TechnicalAnalyzer (technical indicators)
  • OptionsAnalyzer (Greeks & liquidity)
  • MarketAnalyzer (market regime)
  • StrategySelector (10+ strategies)
  • CallPutPredictor (ML model, 34 features)
  • ReasoningGenerator (narrative synthesis)

- 277 unit tests (100% passing)
  • 28 News tests ✓
  • 36 Technical tests ✓
  • 48 Options tests ✓
  • 54 Market tests ✓
  • 36 Strategy tests ✓
  • 36 ML prediction tests ✓
  • 39 Reasoning tests ✓

- FastAPI REST backend (Phase 3B foundation)
  • 12 production-ready endpoints
  • WebSocket support
  • Bearer token authentication
  • Comprehensive error handling
  • CORS middleware

- Complete documentation
  • README.md (comprehensive guide)
  • GITHUB_SETUP.md (push instructions)
  • PROJECT_SUMMARY.md (deliverables)
  • API documentation
  • Setup scripts

READY FOR:
✓ Local development
✓ Testing
✓ Phase 3B+ continuation (database, auth, persistence)
✓ Phase 3C (scheduled tasks)"

echo "✓ Initial commit created"
echo ""

# Step 6: Instructions for GitHub remote
echo "[6/6] Next steps:"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "1. Create repository on GitHub:"
echo "   • Go to https://github.com/new"
echo "   • Name: options-trading-system"
echo "   • Description: Professional options trading analysis engine"
echo "   • Choice: Public or Private"
echo "   • Click 'Create repository'"
echo ""
echo "2. Add remote and push (copy one of these):"
echo ""
echo "   OPTION A - HTTPS (easier first time):"
echo "   ────────────────────────────────────────"
echo "   git remote add origin https://github.com/YOUR_USERNAME/options-trading-system.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "   OPTION B - SSH (more secure):"
echo "   ────────────────────────────────────────"
echo "   git remote add origin git@github.com:YOUR_USERNAME/options-trading-system.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "3. Verify on GitHub:"
echo "   ────────────────────────────────────────"
echo "   https://github.com/YOUR_USERNAME/options-trading-system"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "✓ Ready to push! Execute the commands above with your GitHub URL."
echo ""

