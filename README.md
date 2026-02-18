# Sitemapping

End-to-end account targeting pipeline for Claude Code. Takes a target account (or a batch via CSV), finds their manufacturing facility locations, enriches people via Clay, matches people to nearby facilities, and outputs a capped lead list ready for outreach.

![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-blue) ![License](https://img.shields.io/badge/License-Private-gray)

## How It Works

The pipeline runs in 5 phases, fully orchestrated by Claude Code:

```
Single account ──► /sitemapping (interactive, you see every step)
                        │
Multiple accounts ──► sitemapping-agent (batch, runs in background)
                        │
                   (both follow the same phases below)
                        │
                        ▼
Phase 1: Extract Locations
    Claude researches each account's manufacturing/production
    facilities using web search, company websites, and Google
    Places API. Outputs a location CSV per account.
    │
    ▼
Phase 2: Import to Clay
    Accounts are pushed to Clay for LinkedIn enrichment.
    Clay finds relevant people (ops, maintenance, engineering)
    and enriches with job titles, personas, and contact info.
    │
    ▼
Phase 3: Poll for Enrichment
    Automatically polls until Clay finishes processing.
    │
    ▼
Phase 4: Export & Review
    Downloads the enriched people list and shows a per-account
    breakdown. You choose lead cap and prioritization method.
    │
    ▼
Phase 5: Match & Cap
    Matches each person's location to the nearest facility,
    filters to matched leads only, and caps at your chosen
    limit per location using seniority + persona scoring.
    │
    ▼
 Capped List (final output)
```

### Location Extraction (`/sites`)

For each account, Claude classifies the company into one of four scenarios:

- **Scenario A** — Locations listed on a single page (direct extraction)
- **Scenario B** — Locations behind an interactive map (headless browser)
- **Scenario C** — No centralized list (Google Places API search by company name)
- **Scenario D** — Partial data on site + Places API to fill gaps

### People-to-Location Matching (`/mapping`)

Each person's city/state is matched against facility locations for their account:

- **Exact match** — city and state both match
- **Fuzzy match** — close city name + state match
- **State-only match** — only used when one facility in that state
- **No match** — filtered out of the final list

### Lead Capping

Locations with more people than the cap are trimmed using seniority priority:

1. **Tier 1** — Director+ titles with a target persona
2. **Tier 2A** — Plant Manager / General Manager
3. **Tier 2B** — Manager (any)
4. **Tier 2C** — All others

Within each tier, leads are ranked by persona relevance score.

## Skills & Agents

### Slash Commands (interactive)

| Skill | Description |
|-------|-------------|
| `/sitemapping` | Full pipeline for a **single account** — interactive, step-by-step |
| `/sites` | Extract facility locations for a single company |
| `/mapping` | Match people to locations and build the capped list |

### Agents (background)

| Agent | Description |
|-------|-------------|
| `sitemapping-agent` | Full pipeline for **multiple accounts** via CSV — runs in background, returns results when done |

**When to use which:**
- One account → `/sitemapping` (you watch it run, can interject)
- Multiple accounts → ask Claude to run the `sitemapping-agent` (batch mode, non-blocking)

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

Skills auto-load from `.claude/commands/` and the agent auto-loads from `.claude/agents/` — no extra setup needed. Run `git pull` to get updates.

## Output Files

All output is saved to `~/sitemapping/<campaign-name>/`:

| File | Description |
|------|-------------|
| `account locations/*.csv` | Facility locations per account |
| `People List.csv` | Raw enriched people from Clay |
| `People List - Enriched.csv` | People with matched location columns |
| `People List - Matched Leads (New).csv` | Only people near a known facility |
| `People List - Matched Leads (New) - Capped.csv` | Final list, capped per location |

## Resuming

Long campaigns can be resumed across sessions:

```
/sitemapping --resume <campaign-id>
```

The pipeline picks up where it left off — skipping accounts that already have location CSVs and checking Clay enrichment status.

## Requirements

- [Claude Code](https://claude.ai/claude-code) installed with an active subscription
