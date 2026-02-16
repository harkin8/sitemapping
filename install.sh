#!/bin/bash
set -e

REPO="https://raw.githubusercontent.com/harkin8/sitemapping/main"
DIR="$HOME/.claude/commands"

mkdir -p "$DIR"

echo "Installing sitemapping skills..."
curl -fsSL "$REPO/.claude/commands/sitemapping.md" -o "$DIR/sitemapping.md"
curl -fsSL "$REPO/.claude/commands/sites.md" -o "$DIR/sites.md"
curl -fsSL "$REPO/.claude/commands/mapping.md" -o "$DIR/mapping.md"

echo "Done! 3 skills installed to ~/.claude/commands/"
echo ""
echo "Usage: open Claude Code and run /sitemapping"
