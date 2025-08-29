# Proxyman SSL Certificate Conflict - Quick Fix Guide

## Problem
Proxyman's SSL certificate setup interferes with curl commands used by the Ghost Backend Framework's MacPorts installation scripts, causing this error:
```
curl: (77) error setting certificate verify locations: CAfile: /Users/[username]/.proxyman/proxyman-ca.pem CApath: none
```

## Solutions (Choose One)

### Solution 1: Use the Proxyman-Safe Make Wrapper (Recommended)
```bash
# Instead of: make db/install
./make-safe.sh db/install

# Instead of: make db/create
./make-safe.sh db/create
```

### Solution 2: Temporarily Disable Proxyman SSL
```bash
# Save current environment
export SAVED_CURL_CA_BUNDLE="$CURL_CA_BUNDLE"

# Clear Proxyman SSL settings
unset CURL_CA_BUNDLE SSL_CERT_DIR SSL_CERT_FILE

# Run your make command
make db/install

# Restore Proxyman settings
export CURL_CA_BUNDLE="$SAVED_CURL_CA_BUNDLE"
```

### Solution 3: Use direnv with Enhanced .envrc
```bash
# Install direnv if not already installed
brew install direnv

# Allow the updated .envrc
direnv allow

# Now make commands should work normally
make db/install
```

### Solution 4: One-Time Fix in New Terminal
```bash
# Open a new terminal (without Proxyman environment)
# Navigate to project directory
cd /Users/grayghostdataconsultants/Ghost

# Run the problematic command
make db/install
```

## Verification
After applying any solution, test with:
```bash
curl -fsSL https://api.github.com/repos/macports/macports-base/releases/latest
```

If this works without error, your SSL configuration is fixed.

## Files Modified
- `scripts/macports/install_macports.sh` - Enhanced SSL handling
- `scripts/macports/env_helpers.sh` - Added safe_curl function  
- `.envrc` - Added Proxyman detection and management
- `make-safe.sh` - Wrapper script for SSL-safe make commands

## Prevention
The enhanced scripts now automatically detect and handle Proxyman SSL conflicts, so this issue should not occur again.
