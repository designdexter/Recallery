#!/bin/bash
# Recallery Mac Setup Script
# Run this once to install the watcher as a background service

set -e

echo ""
echo "╔══════════════════════════════════════╗"
echo "║       Recallery Mac Setup            ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── Check Ollama ──────────────────────────────────────────────────────────────
if ! command -v ollama &>/dev/null; then
    echo "Error: Ollama is not installed."
    echo "Install it from https://ollama.com and run this script again."
    exit 1
fi

# Check if the model is available
MODEL="gemma3:4b"
if ! ollama list | grep -q "$MODEL"; then
    echo "Pulling vision model ($MODEL)… this is a one-time ~3GB download."
    ollama pull "$MODEL"
fi

echo "✓ Ollama and $MODEL are ready"

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WATCHER_SCRIPT="$SCRIPT_DIR/recallery_watcher.py"
PLIST_NAME="com.recallery.watcher"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"
USERNAME=$(whoami)

# ── Create LaunchAgents folder if needed ──────────────────────────────────────
mkdir -p "$HOME/Library/LaunchAgents"

# ── Write the plist with real values ─────────────────────────────────────────
cat > "$PLIST_DEST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.recallery.watcher</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$WATCHER_SCRIPT</string>
    </array>

    <key>EnvironmentVariables</key>
    <dict>
        <key>OLLAMA_URL</key>
        <string>http://localhost:11434</string>
        <key>OLLAMA_MODEL</key>
        <string>gemma3:4b</string>
    </dict>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>/Users/$USERNAME/Library/Logs/recallery.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/$USERNAME/Library/Logs/recallery.log</string>
</dict>
</plist>
EOF

echo "✓ LaunchAgent plist written"

# ── Load the service ──────────────────────────────────────────────────────────
# Unload first in case it was already loaded
launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"

echo "✓ Recallery watcher started"
echo ""
echo "══════════════════════════════════════════"
echo "  Recallery is running in the background"
echo ""
echo "  Watching : ~/Desktop"
echo "  Sorting into : ~/Pictures/Recallery/"
echo "  Model   : gemma3:4b (local, via Ollama)"
echo ""
echo "  New screenshots will be auto-sorted"
echo "  into named folders instantly."
echo ""
echo "  Logs: ~/Library/Logs/recallery.log"
echo "══════════════════════════════════════════"
echo ""
