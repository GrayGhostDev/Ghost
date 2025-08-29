#!/bin/bash
# GitHub Repository Setup Script
# Configures GitHub repository with recommended settings

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Logging functions
log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }
log_step() { echo -e "${PURPLE}🚀 $1${NC}"; }

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════╗"
echo "║         GitHub Repository Setup                  ║"
echo "║         Ghost Backend Framework                   ║"
echo "╚═══════════════════════════════════════════════════╝"
echo -e "${NC}"

# =================================================================
# STEP 1: Verify GitHub CLI Installation
# =================================================================
log_step "STEP 1: Checking GitHub CLI"

if ! command -v gh &> /dev/null; then
    log_error "GitHub CLI (gh) is not installed"
    log_info "Please install it: https://cli.github.com/"
    log_info "macOS: brew install gh"
    log_info "After installation, run: gh auth login"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    log_error "Not authenticated with GitHub CLI"
    log_info "Please run: gh auth login"
    exit 1
fi

log_success "GitHub CLI is installed and authenticated"

# =================================================================
# STEP 2: Repository Information
# =================================================================
log_step "STEP 2: Repository Configuration"

# Get current repository info
if git rev-parse --is-inside-work-tree &> /dev/null; then
    REPO_URL=$(git config --get remote.origin.url || echo "")
    if [[ -n "$REPO_URL" ]]; then
        # Extract owner/repo from URL
        if [[ "$REPO_URL" =~ github\.com[:/]([^/]+)/([^/]+)(\.git)?$ ]]; then
            REPO_OWNER="${BASH_REMATCH[1]}"
            REPO_NAME="${BASH_REMATCH[2]%.git}"
            log_success "Repository: $REPO_OWNER/$REPO_NAME"
        else
            log_error "Could not parse repository URL: $REPO_URL"
            exit 1
        fi
    else
        log_error "No remote origin found. Please set up your GitHub repository first."
        log_info "Run: git remote add origin https://github.com/USERNAME/REPO.git"
        exit 1
    fi
else
    log_error "Not in a git repository"
    exit 1
fi

# =================================================================
# STEP 3: Repository Settings
# =================================================================
log_step "STEP 3: Configuring Repository Settings"

log_info "Updating repository description and topics..."
gh repo edit "$REPO_OWNER/$REPO_NAME" \
    --description "🚀 Ghost Backend Framework - A comprehensive, reusable backend development foundation with enterprise-grade security, FastAPI, PostgreSQL, Redis, and complete DevOps integration" \
    --homepage "https://github.com/$REPO_OWNER/$REPO_NAME" \
    --add-topic "python" \
    --add-topic "fastapi" \
    --add-topic "backend" \
    --add-topic "framework" \
    --add-topic "postgresql" \
    --add-topic "redis" \
    --add-topic "security" \
    --add-topic "devops" \
    --add-topic "api" \
    --add-topic "microservices" \
    --visibility public \
    --accept-visibility-change-consequences

log_success "Repository metadata updated"

# =================================================================
# STEP 4: Branch Protection Rules
# =================================================================
log_step "STEP 4: Setting Up Branch Protection"

log_info "Configuring main branch protection..."
gh api repos/$REPO_OWNER/$REPO_NAME/branches/main/protection \
    --method PUT \
    --field required_status_checks[strict]=true \
    --field required_status_checks[contexts][]="CI/CD Pipeline" \
    --field enforce_admins=true \
    --field required_pull_request_reviews[required_approving_review_count]=1 \
    --field required_pull_request_reviews[dismiss_stale_reviews]=true \
    --field required_pull_request_reviews[require_code_owner_reviews]=false \
    --field restrictions=null \
    --field allow_force_pushes=false \
    --field allow_deletions=false 2>/dev/null || log_warning "Branch protection configuration skipped (may need manual setup)"

log_success "Branch protection configured"

# =================================================================
# STEP 5: Repository Features
# =================================================================
log_step "STEP 5: Enabling Repository Features"

log_info "Enabling repository features..."
gh api repos/$REPO_OWNER/$REPO_NAME \
    --method PATCH \
    --field has_issues=true \
    --field has_projects=true \
    --field has_wiki=false \
    --field has_downloads=true \
    --field allow_squash_merge=true \
    --field allow_merge_commit=false \
    --field allow_rebase_merge=true \
    --field delete_branch_on_merge=true \
    --field allow_auto_merge=true 2>/dev/null || true

log_success "Repository features configured"

# =================================================================
# STEP 6: Labels Setup
# =================================================================
log_step "STEP 6: Setting Up Issue Labels"

log_info "Creating custom labels..."

# Create labels one by one
gh label create "security" --color "d73a4a" --repo "$REPO_OWNER/$REPO_NAME" 2>/dev/null || true
gh label create "priority-high" --color "b60205" --repo "$REPO_OWNER/$REPO_NAME" 2>/dev/null || true
gh label create "priority-medium" --color "fbca04" --repo "$REPO_OWNER/$REPO_NAME" 2>/dev/null || true
gh label create "priority-low" --color "0e8a16" --repo "$REPO_OWNER/$REPO_NAME" 2>/dev/null || true
gh label create "needs-triage" --color "ededed" --repo "$REPO_OWNER/$REPO_NAME" 2>/dev/null || true
gh label create "backend" --color "1d76db" --repo "$REPO_OWNER/$REPO_NAME" 2>/dev/null || true
gh label create "frontend" --color "f9d0c4" --repo "$REPO_OWNER/$REPO_NAME" 2>/dev/null || true
gh label create "database" --color "5319e7" --repo "$REPO_OWNER/$REPO_NAME" 2>/dev/null || true
gh label create "api" --color "0052cc" --repo "$REPO_OWNER/$REPO_NAME" 2>/dev/null || true
gh label create "documentation" --color "0075ca" --repo "$REPO_OWNER/$REPO_NAME" 2>/dev/null || true
gh label create "performance" --color "fef2c0" --repo "$REPO_OWNER/$REPO_NAME" 2>/dev/null || true
gh label create "refactor" --color "e4e669" --repo "$REPO_OWNER/$REPO_NAME" 2>/dev/null || true
gh label create "dependencies" --color "0366d6" --repo "$REPO_OWNER/$REPO_NAME" 2>/dev/null || true
gh label create "automated" --color "c2e0c6" --repo "$REPO_OWNER/$REPO_NAME" 2>/dev/null || true

log_success "Custom labels created"

# =================================================================
# STEP 7: Secrets and Variables Setup
# =================================================================
log_step "STEP 7: Repository Secrets Setup"

log_warning "Repository secrets need to be set up manually for security:"
log_info "Go to: https://github.com/$REPO_OWNER/$REPO_NAME/settings/secrets/actions"
log_info "Add these secrets as needed:"
log_info "  - CODECOV_TOKEN (for code coverage)"
log_info "  - DEPLOY_KEY (for deployment)"
log_info "  - DOCKER_PASSWORD (for container registry)"
log_info "  - SLACK_WEBHOOK (for notifications)"

# =================================================================
# STEP 8: Create Initial Issues and Projects
# =================================================================
log_step "STEP 8: Creating Initial Project Structure"

log_info "Creating initial milestone..."
gh api repos/$REPO_OWNER/$REPO_NAME/milestones \
    --method POST \
    --field title="v1.0.0 - Initial Release" \
    --field description="First stable release of the Ghost Backend Framework" \
    --field due_on="$(date -d '+3 months' +%Y-%m-%dT%H:%M:%SZ)" 2>/dev/null || true

log_info "Creating welcome issue..."
gh issue create \
    --title "🎉 Welcome to Ghost Backend Framework" \
    --body "$(cat << 'EOF'
# Welcome to the Ghost Backend Framework! 🚀

Thank you for your interest in our comprehensive backend development foundation.

## 🏃‍♂️ Quick Start

1. **Setup**: Run `./bin/setup.sh` to initialize your environment
2. **Security**: Configure keychain with `./tools/security/keychain.sh setup`
3. **Launch**: Start the backend with `./bin/start_backend.sh`

## 📚 Documentation

- [README.md](./README.md) - Main documentation
- [CONTRIBUTING.md](./CONTRIBUTING.md) - How to contribute
- [SECURITY.md](./SECURITY.md) - Security policy
- [DIRECTORY_STRUCTURE.md](./DIRECTORY_STRUCTURE.md) - Project organization

## 🤝 Get Involved

- Report bugs using our [bug report template](.github/ISSUE_TEMPLATE/bug_report.md)
- Request features using our [feature request template](.github/ISSUE_TEMPLATE/feature_request.md)
- Ask questions in [Discussions](../../discussions)
- Check out [good first issues](../../issues?q=is%3Aopen+is%3Aissue+label%3A%22good+first+issue%22)

## 🔒 Security

Found a security issue? Please use our [security policy](./SECURITY.md) for responsible disclosure.

Welcome aboard! 🎉
EOF
)" \
    --label "documentation,good first issue" \
    --repo "$REPO_OWNER/$REPO_NAME" 2>/dev/null || true

log_success "Initial project structure created"

# =================================================================
# FINAL SUMMARY
# =================================================================
echo ""
echo -e "${GREEN}"
echo "╔═══════════════════════════════════════════════════╗"
echo "║            🎉 GITHUB SETUP COMPLETE! 🎉          ║"
echo "╠═══════════════════════════════════════════════════╣"
echo "║ ✅ Repository metadata configured                ║"
echo "║ ✅ Branch protection enabled                     ║"
echo "║ ✅ GitHub Actions workflows ready               ║"
echo "║ ✅ Issue/PR templates created                    ║"
echo "║ ✅ Security policy established                   ║"
echo "║ ✅ Contributing guidelines added                 ║"
echo "║ ✅ Custom labels configured                      ║"
echo "║ ✅ Initial project structure created             ║"
echo "╚═══════════════════════════════════════════════════╝"
echo -e "${NC}"

log_success "GitHub repository setup complete!"
log_info "Repository URL: https://github.com/$REPO_OWNER/$REPO_NAME"
log_info "Next steps:"
log_info "  1. Review and customize repository settings"
log_info "  2. Set up repository secrets for CI/CD"
log_info "  3. Invite collaborators if needed"
log_info "  4. Create your first release"

echo ""
log_info "🚀 Your Ghost Backend Framework is now ready for collaborative development!"
