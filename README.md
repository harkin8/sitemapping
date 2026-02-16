# Sitemapping

End-to-end account targeting pipeline for Claude Code. Takes a list of accounts, extracts facility locations, enriches people via Clay, matches people to locations, and outputs a capped lead list.

![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-blue) ![License](https://img.shields.io/badge/License-Private-gray)

## Skills

| Skill | Description |
|-------|-------------|
| `/sitemapping` | Full pipeline orchestrator — accounts to capped list |
| `/sites` | Extract manufacturing facility locations for a company |
| `/mapping` | Match people to facility locations and build ATL |

## Installation

### One-Command Install (macOS/Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/harkin8/sitemapping/main/install.sh | bash
```

This installs 3 skill files to `~/.claude/commands/`. Then open Claude Code and run `/sitemapping`.

### Manual Install

```bash
git clone https://github.com/harkin8/sitemapping.git
cd sitemapping
claude
```

Skills auto-load from the repo's `.claude/commands/` directory.

## Requirements

- [Claude Code](https://claude.ai/claude-code) installed with an active subscription
