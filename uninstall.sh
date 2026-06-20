#!/bin/bash
# Recallery Uninstall — stops the background watcher

PLIST_NAME="com.recallery.watcher"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

if [ -f "$PLIST_PATH" ]; then
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    rm "$PLIST_PATH"
    echo "✓ Recallery watcher stopped and removed"
else
    echo "Recallery watcher is not installed"
fi
