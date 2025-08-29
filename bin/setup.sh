#!/bin/bash
# ============================================================================
# GHOST BACKEND FRAMEWORK - QUICK SETUP SCRIPT
# ============================================================================
# This script helps you quickly configure your Ghost Backend Framework

set -e  # Exit on any error

echo "🚀 Ghost Backend Framework - Quick Setup"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_question() {
    echo -e "${BLUE}[QUESTION]${NC} $1"
}

# Check if we're in the Ghost directory
if [ ! -f "pyproject.toml" ] || [ ! -d "src/ghost" ]; then
    print_error "This script must be run from the Ghost Backend Framework root directory"
    exit 1
fi

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1-2)
required_version="3.10"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
    print_error "Python 3.10+ is required. You have Python $python_version"
    exit 1
fi

print_status "Python version check passed: $python_version"

# Function to generate secure keys
generate_secret_key() {
    python3 -c "import secrets; print(secrets.token_urlsafe(64))"
}

generate_api_key() {
    python3 -c "import secrets; print('api_' + secrets.token_hex(32))"
}

# Function to prompt for input with default
prompt_with_default() {
    local prompt="$1"
    local default="$2"
    local value
    
    read -p "$(echo -e "${BLUE}$prompt${NC} [$default]: ")" value
    echo "${value:-$default}"
}

# Function to prompt for password (hidden input)
prompt_password() {
    local prompt="$1"
    local value
    
    read -s -p "$(echo -e "${BLUE}$prompt${NC}: ")" value
    echo
    echo "$value"
}

# Function to prompt yes/no
prompt_yes_no() {
    local prompt="$1"
    local default="$2"
    local response
    
    while true; do
        read -p "$(echo -e "${BLUE}$prompt${NC} (y/n) [$default]: ")" response
        response="${response:-$default}"
        case "$response" in
            [Yy]|[Yy][Ee][Ss]) return 0 ;;
            [Nn]|[Nn][Oo]) return 1 ;;
            *) echo "Please answer yes or no." ;;
        esac
    done
}

echo
print_status "Starting interactive configuration..."
echo

# Basic project information
echo "📝 Basic Project Configuration"
echo "-----------------------------"
PROJECT_NAME=$(prompt_with_default "Project name" "MyApp Backend")
ENVIRONMENT=$(prompt_with_default "Environment (development/staging/production)" "development")

# Database configuration
echo
echo "🗄️ Database Configuration"
echo "------------------------"
print_question "Which database would you like to use?"
echo "1) PostgreSQL (recommended for production)"
echo "2) SQLite (good for development)"
echo "3) I'll configure it later"

read -p "$(echo -e "${BLUE}Choice${NC} [1]: ")" db_choice
db_choice="${db_choice:-1}"

case "$db_choice" in
    1)
        DB_DRIVER="postgresql"
        DB_HOST=$(prompt_with_default "Database host" "localhost")
        DB_PORT=$(prompt_with_default "Database port" "5432")
        DB_NAME=$(prompt_with_default "Database name" "ghost_db")
        DB_USER=$(prompt_with_default "Database user" "postgres")
        DB_PASSWORD=$(prompt_password "Database password")
        DATABASE_URL="postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME"
        ;;
    2)
        DB_DRIVER="sqlite"
        DB_NAME=$(prompt_with_default "SQLite database file" "ghost.db")
        DATABASE_URL="sqlite:///./$DB_NAME"
        ;;
    3)
        DATABASE_URL="sqlite:///./ghost.db"  # Default fallback
        ;;
esac

# Redis configuration
echo
if prompt_yes_no "Do you want to configure Redis for caching?" "y"; then
    REDIS_HOST=$(prompt_with_default "Redis host" "localhost")
    REDIS_PORT=$(prompt_with_default "Redis port" "6379")
    REDIS_DB=$(prompt_with_default "Redis database number" "0")
    
    if prompt_yes_no "Does Redis require a password?" "n"; then
        REDIS_PASSWORD=$(prompt_password "Redis password")
        REDIS_URL="redis://:$REDIS_PASSWORD@$REDIS_HOST:$REDIS_PORT/$REDIS_DB"
    else
        REDIS_URL="redis://$REDIS_HOST:$REDIS_PORT/$REDIS_DB"
    fi
else
    REDIS_URL="redis://localhost:6379/0"
fi

# API configuration
echo
echo "🌐 API Configuration"
echo "-------------------"
API_HOST=$(prompt_with_default "API host" "0.0.0.0")
API_PORT=$(prompt_with_default "API port" "8000")

# Security configuration
echo
echo "🔐 Security Configuration"
echo "------------------------"
print_warning "Generating secure secret keys..."

JWT_SECRET_KEY=$(generate_secret_key)
API_KEY=$(generate_api_key)
print_status "Generated JWT secret key and API key"

# External APIs
echo
echo "🔌 External API Configuration (Optional)"
echo "---------------------------------------"
OPENAI_API_KEY=""
ANTHROPIC_API_KEY=""

if prompt_yes_no "Do you want to configure OpenAI API?" "n"; then
    OPENAI_API_KEY=$(prompt_password "OpenAI API Key")
fi

if prompt_yes_no "Do you want to configure Anthropic API?" "n"; then
    ANTHROPIC_API_KEY=$(prompt_password "Anthropic API Key")
fi

# Create .env file
echo
print_status "Creating .env file..."

cat > .env << EOF
# ============================================================================
# GHOST BACKEND FRAMEWORK - ENVIRONMENT CONFIGURATION
# ============================================================================
# Generated by setup script on $(date)

# Basic settings
ENVIRONMENT=$ENVIRONMENT
DEBUG=$([ "$ENVIRONMENT" = "development" ] && echo "true" || echo "false")
PROJECT_NAME=$PROJECT_NAME

# Database configuration
DATABASE_URL=$DATABASE_URL

# Redis configuration
REDIS_URL=$REDIS_URL

# API configuration
API_HOST=$API_HOST
API_PORT=$API_PORT
API_KEY=$API_KEY

# Security configuration
JWT_SECRET_KEY=$JWT_SECRET_KEY
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# External API keys
OPENAI_API_KEY=$OPENAI_API_KEY
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY

# Logging configuration
LOG_LEVEL=$([ "$ENVIRONMENT" = "development" ] && echo "DEBUG" || echo "INFO")
LOG_FILE=logs/ghost.log

# CORS configuration (adjust for your frontend)
API_CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
EOF

print_status ".env file created successfully!"

# Set secure permissions
chmod 600 .env
print_status "Set secure permissions (600) on .env file"

# Create logs directory
mkdir -p logs
print_status "Created logs directory"

# Create uploads directory
mkdir -p uploads
print_status "Created uploads directory"

# Install dependencies
echo
if prompt_yes_no "Do you want to install Python dependencies now?" "y"; then
    print_status "Installing dependencies..."
    
    if [ "$ENVIRONMENT" = "development" ]; then
        pip install -e ".[dev,all]"
    else
        pip install -e ".[all]"
    fi
    
    print_status "Dependencies installed successfully!"
fi

# Test the configuration
echo
if prompt_yes_no "Do you want to test the configuration?" "y"; then
    print_status "Testing configuration..."
    
    python3 -c "
from src.ghost import get_available_features, Config, setup_logging, get_logger
print('🧪 Testing Ghost Backend Framework...')
features = get_available_features()
print(f'📦 Available features: {features}')
config = Config()
setup_logging(config.logging)
logger = get_logger('setup')
logger.info('✅ Configuration test completed successfully!')
print('🎉 Ghost Backend Framework is working perfectly!')
" 2>/dev/null || print_error "Configuration test failed. Please check your settings."
fi

# Summary
echo
echo "🎉 Setup Complete!"
echo "=================="
print_status "Your Ghost Backend Framework is configured and ready to use!"
echo
echo "📝 What was created:"
echo "  • .env file with your configuration"
echo "  • logs/ directory for application logs"
echo "  • uploads/ directory for file uploads"
echo
echo "🚀 Next steps:"
echo "  1. Review and adjust the .env file as needed"
echo "  2. Set up your database (see docs/DATABASE_SETUP.md)"
echo "  3. Start your application:"
echo "     python -m src.ghost.api"
echo "  4. Visit http://localhost:$API_PORT to test your API"
echo
echo "📚 Documentation:"
echo "  • README.md - General usage guide"
echo "  • docs/DATABASE_SETUP.md - Database setup guide"
echo "  • docs/SECURITY_GUIDE.md - Security configuration"
echo "  • docs/DEPLOYMENT_GUIDE.md - Deployment instructions"
echo
print_warning "Remember to:"
print_warning "• Never commit your .env file to version control"
print_warning "• Use strong passwords for production databases"
print_warning "• Configure SSL/HTTPS for production deployments"
echo
print_status "Happy coding with Ghost Backend Framework! 👻"
