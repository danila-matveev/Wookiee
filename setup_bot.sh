#!/bin/bash
# Wookiee Bot Setup Script

set -e

echo "🤖 Wookiee Analytics Bot - Setup Script"
echo "========================================"
echo ""

# Check if Python 3.11+ is installed
echo "✓ Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.11 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "  Found Python $PYTHON_VERSION"

# Create virtual environment
echo ""
echo "✓ Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  Virtual environment created"
else
    echo "  Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo "✓ Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo ""
echo "✓ Installing dependencies..."
pip install --upgrade pip
pip install -r bot/requirements.txt
echo "  Dependencies installed"

# Create .env from example if doesn't exist
echo ""
if [ ! -f "bot/.env" ]; then
    echo "✓ Creating .env file from example..."
    cp bot/.env.example bot/.env
    echo "  .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Edit bot/.env and fill in your tokens and API keys!"
    echo ""
else
    echo "✓ .env file already exists"
fi

# Create directories
echo ""
echo "✓ Creating data directories..."
mkdir -p bot/data bot/logs
echo "  Directories created"

# Generate password hash helper
echo ""
echo "✓ Would you like to generate a password hash now? (y/n)"
read -r GENERATE_HASH

if [ "$GENERATE_HASH" = "y" ] || [ "$GENERATE_HASH" = "Y" ]; then
    echo ""
    echo "Enter password for bot access:"
    read -s PASSWORD
    echo ""
    echo "Generating hash..."
    HASH=$(python3 -c "import bcrypt; print(bcrypt.hashpw(b'$PASSWORD', bcrypt.gensalt()).decode())")
    echo ""
    echo "✅ Password hash generated!"
    echo "Copy this to BOT_PASSWORD_HASH in bot/.env:"
    echo ""
    echo "$HASH"
    echo ""
fi

# Check configuration
echo ""
echo "✓ Checking configuration..."

if grep -q "YOUR_BOT_TOKEN_HERE" bot/.env 2>/dev/null; then
    echo "⚠️  WARNING: TELEGRAM_BOT_TOKEN not configured in bot/.env"
fi

if grep -q "your_zai_api_key" bot/.env 2>/dev/null; then
    echo "⚠️  WARNING: ZAI_API_KEY not configured in bot/.env"
fi

if grep -q "your_claude_api_key" bot/.env 2>/dev/null; then
    echo "⚠️  WARNING: CLAUDE_API_KEY not configured in bot/.env"
fi

# Final instructions
echo ""
echo "========================================"
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit bot/.env and fill in all required tokens and API keys"
echo "2. Activate virtual environment: source venv/bin/activate"
echo "3. Run the bot: python -m bot.main"
echo ""
echo "For deployment on server, see DEPLOYMENT.md"
echo "========================================"
