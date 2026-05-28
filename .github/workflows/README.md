# GitHub Actions Workflows

This directory contains automated CI/CD workflows for the Options Trading System.

## Workflows

### `tests.yml` - Automated Testing
- **Trigger**: Push/PR to main or develop
- **Python versions**: 3.9, 3.10, 3.11
- **Tests**: 277 unit tests
- **Coverage**: Codecov integration

### `code-quality.yml` - Code Quality & Security
- **Trigger**: Push/PR to main or develop
- **Checks**: 
  - Black (code formatting)
  - isort (import sorting)
  - flake8 (linting)
  - bandit (security)
  - mypy (type checking)
  - pip-audit (dependency vulnerabilities)

### `deploy.yml` - Deployment
- **Trigger**: Push to main
- **Steps**:
  1. Run all tests
  2. Build Docker image
  3. Create deployment artifact
  4. Generate GitHub release
  5. Upload artifacts

## Quick Reference

### View Workflow Status
```
https://github.com/YOUR_USERNAME/options-trading-system/actions
```

### Re-run Failed Workflow
1. Go to Actions tab
2. Click failed workflow
3. Click "Re-run jobs"

### Skip CI
Add `[skip ci]` to commit message:
```bash
git commit -m "Quick fix [skip ci]"
```

### Manual Deployment
1. Actions → Deploy
2. "Run workflow" button
3. Select branch
4. Click "Run workflow"

## Customization

### Change Python Versions
Edit `tests.yml`:
```yaml
python-version: ['3.9', '3.10', '3.11']
```

### Add New Checks
Edit respective workflow file and add new job.

### Integrate with External Services
Add secrets in GitHub Settings → Secrets → Actions

## Workflow Files

```
.github/
├── workflows/
│   ├── tests.yml           # Testing pipeline
│   ├── code-quality.yml    # Quality checks
│   └── deploy.yml          # Deployment pipeline
└── README.md               # This file
```

## Status Badges

Add to README.md:

```markdown
![Tests](https://github.com/YOUR_USERNAME/options-trading-system/actions/workflows/tests.yml/badge.svg)
![Code Quality](https://github.com/YOUR_USERNAME/options-trading-system/actions/workflows/code-quality.yml/badge.svg)
```

## Environment Secrets

Configure in GitHub Settings → Secrets → Actions:

- `DEPLOY_KEY` - SSH key for deployment
- `DATABASE_URL` - Production database URL
- `DOCKER_USERNAME` - Docker Hub username
- `DOCKER_PASSWORD` - Docker Hub token

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Workflow Syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
- [Events that trigger workflows](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows)
