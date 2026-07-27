# 🔐 Ghost Backend Framework - Secure Credential Management

## 🚨 CRITICAL SECURITY NOTICE

**Your codebase had EXPOSED API KEYS that have been secured!**

The following files have been updated to use secure keychain-based credential management:
- `.env` → `.env.secure` (secure template)
- `config.production.yaml` (environment variable references)
- `run_api.sh` (keychain integration) 
- `docker-compose.yml` (environment variable references)
- `tools/start_multi_backend.py` (keychain loader)
- `scripts/complete_setup.py` (secure templates)

## 🔑 Quick Start - Secure Credential Setup

### 1. Install Credentials in macOS Keychain

```bash
# Setup all credentials securely in keychain
./scripts/secrets/keychain.sh setup

# This will prompt you to enter your API keys securely:
# - Anthropic API Key (sk-ant-...)
# - OpenAI API Key (sk-...)  
# - GitHub PAT (ghp_...)
# - Brave API Key
# - SendGrid API Key
# - And other external API credentials
```

### 2. Generate Runtime Environment

```bash
# Generate the runtime environment loader
./scripts/secrets/keychain.sh runtime-env

# This creates .env.runtime that loads credentials from keychain
```

### 3. Start Your Application Securely

```bash
# Option 1: Use the secure API runner
./run_api.sh

# Option 2: Load credentials in your shell
source .env.runtime
python -m uvicorn src.ghost.api:app --reload

# Option 3: Docker with secure environment
source .env.runtime
docker-compose up
```

## 🔐 Keychain Management Commands

```bash
# Setup all credentials (interactive)
./scripts/secrets/keychain.sh setup

# List stored credentials (without showing values)
./scripts/secrets/keychain.sh list

# Export credentials to environment
source <(./scripts/secrets/keychain.sh export)

# Generate runtime environment file
./scripts/secrets/keychain.sh runtime-env

# Remove all stored credentials
./scripts/secrets/keychain.sh cleanup
```

## 🛡️ Security Features

### ✅ What's Now Secure

1. **No Hardcoded Secrets**: All API keys use environment variable references
2. **Keychain Integration**: Credentials stored in macOS Keychain Services
3. **Runtime Loading**: Secrets loaded only when needed
4. **Secure Generation**: Auto-generated secure JWT secrets and API keys
5. **Development Safety**: `.env.runtime` excluded from git
6. **Docker Integration**: Environment variable passthrough

### ⚠️ CRITICAL - Next Steps Required

1. **Revoke Exposed Keys**: The following API keys were found exposed and should be revoked:
   - Anthropic API Key: `sk-ant-admin01-nRD0KZkk...` 
   - GitHub PAT: `ghp_qYDj7StKxZrqQ6YyK...`
   - Brave API Key: `BSAQRnhgYzC94_lX5bxwG...`

2. **Generate New Keys**: Create fresh API keys from the respective services

3. **Update Keychain**: Store the new keys using `./scripts/secrets/keychain.sh setup`

## 📁 File Structure Changes

```
📁 Your Project/
├── .env.secure              ← Secure template (use this pattern)  
├── .env.docker.example      ← Docker environment template
├── .env.runtime             ← Generated runtime loader (git ignored)
├── config.production.yaml   ← Updated with ${ENV_VAR} references
├── run_api.sh               ← Updated with keychain loading
├── docker-compose.yml       ← Updated with env var references
├── tools/
│   └── start_multi_backend.py ← Updated keychain loader location
├── scripts/secrets/
│   ├── keychain.sh          ← Keychain management utility
│   └── runtime_env.sh       ← Runtime environment helper
└── 🚨 .env (REMOVED)        ← Old file with exposed keys
```

## 🔄 Migration from Old System

If you have an existing `.env` file with credentials:

1. **Backup your keys** (copy them temporarily)
2. **Run secure setup**: `./scripts/secrets/keychain.sh setup`
3. **Enter your API keys** when prompted
4. **Test the system**: `./run_api.sh`
5. **Delete old `.env`** file once confirmed working

## 🐳 Docker Usage

### Development with Docker

```bash
# Generate runtime environment
./scripts/secrets/keychain.sh runtime-env

# Load credentials and start containers  
source .env.runtime
docker-compose up
```

### Production Docker

```bash
# Create production environment file from template
cp .env.docker.example .env

# Edit .env with your secure values (or use keychain references)
# Deploy with your production Docker orchestration
```

## 🔍 Verification

Verify your setup is secure:

```bash
# Check that no secrets are exposed in files
grep -r "sk-" . --exclude-dir=.git --exclude="*.md" || echo "✅ No exposed secrets found"

# List keychain credentials
./scripts/secrets/keychain.sh list

# Test credential loading
source .env.runtime
echo "JWT_SECRET loaded: ${JWT_SECRET:0:10}..." 
echo "API_KEY loaded: ${API_KEY:0:10}..."
```

## 🆘 Troubleshooting

### Keychain Access Denied
```bash
# If macOS denies keychain access, you may need to:
# 1. Open Keychain Access app
# 2. Allow access for Terminal/VS Code
# 3. Re-run: ./scripts/secrets/keychain.sh setup
```

### Environment Not Loading
```bash
# Check if runtime environment exists
ls -la .env.runtime

# Regenerate if missing
./scripts/secrets/keychain.sh runtime-env

# Check keychain entries
./scripts/secrets/keychain.sh list
```

### Docker Environment Issues
```bash
# Make sure you source the environment before docker-compose
source .env.runtime
docker-compose config  # Verify environment substitution
```

## 📞 Support

If you encounter issues:
1. Check the logs in `logs/` directory
2. Verify keychain entries with `./scripts/secrets/keychain.sh list`
3. Test credential loading with `source .env.runtime`
4. Check file permissions on scripts with `ls -la scripts/secrets/`

---

**⚡ You're now running with enterprise-grade credential security!**
