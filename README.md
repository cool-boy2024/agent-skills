# agent-skills

> A lightweight **catalog** of agent skills — and an automated 50k-star curator for cool-boy2024.
> The repo stays under 1MB by storing only metadata for third-party skills; real content is downloaded on demand via `scripts/install.sh`.

This is **cool-boy2024**'s personal skill library. Three goals:
1. **Find** good skills fast — entry point: `find-skills`
2. **Curate** what I actually keep — entry point: `auto-scout` (Claude-side) + `auto-learner` (bash-side)
3. **Audit** what's earning its keep — entry point: `show-installed`

## Quick start

```bash
# See what's in the catalog (with pinned/installed status)
./scripts/install.sh              # no args → list

# Install a skill — auto-pins (won't be removed by clean.sh)
./scripts/install.sh find-skills
./scripts/install.sh grill-me
./scripts/install.sh caveman

# Remove a skill — two-step to be safe
./scripts/unpin.sh caveman        # 1. remove from pinned list
./scripts/clean.sh caveman        # 2. actually delete the files

# Or one-step force-remove (bypasses pin)
./scripts/clean.sh caveman --force

# Install without pinning (rare; for testing)
./scripts/install.sh caveman --no-pin

# Daily discovery (cron-friendly) — gates on 50k+ GitHub stars
./my-skills/auto-learner/scripts/daily_learn.sh "rust async runtime"

# Quarterly full scan — no topic filter, catches old-but-great
./scripts/full_scan.sh

# Inside a Claude session:
#   /show-picks        — see what's awaiting your decision
#   /show-installed    — audit what's installed and how long it's been
#   "装 X" / "留 Y" / "不要 Z"  — natural language actions
```

## The 50k curator system

The user (cool-boy2024) wants a **"more capable version of themselves"** watching GitHub for high-quality projects (50k+ stars), filtering them against their interest profile (programming / stocks-crypto-DeFi-finance-quant / English), and presenting only the worthwhile picks for final say.

```
GitHub 50k+ star universe (~5k repos)
        │
        │  cron daily 9am:     daily_learn.sh (topic-keyword search)
        │  cron quarterly:     full_scan.sh   (broad sweep, no topic)
        │
        ▼
catalog/candidates.md       ← raw queue (bash writes)
        │
        │  every Claude session: auto-scout processes
        │  filters against interest profile
        │  writes structured cards (5 fields)
        │  archives > 90-day entries
        │  commits + pushes
        ▼
catalog/digest.md           ← curated (≤ 30 entries, 3 sections)
  📥 待你决定 / 📦 已装 / 🚫 跳过
        │
        │  user: "装 X" / "留 Y" / "不要 Z"   (or /show-picks)
        ▼
install.sh + auto-pin       ← for skills
🔖 bookmark                 ← for repos (no install)
```

The **50k+ star threshold is a single bar** — no second tier. Lower-star projects don't enter the curator's view under any framing. See `feedback_discovery_threshold.md` in the project memory for the reasoning.

## Pinned skills (default safety net)

Anything you install is **auto-pinned** — meaning `./scripts/clean.sh <name>` will refuse to delete it. This prevents accidental removal.

The reasoning: *"future me, when I want to use a skill, I'll go to our repo to find it. Whether to delete is mine to decide."* Pinning is the technical realization of that.

| State | Effect of `clean.sh <name>` |
|---|---|
| Installed, pinned (default) | **Refuses** (exit 1). Use `unpin.sh` first, or pass `--force`. |
| Installed, not pinned (--no-pin) | Removes it |
| Not installed | No-op |

## Layout

```
agent-skills/
├── README.md                       ← you are here
├── catalog.md                      ← browsable index (hand-curated)
├── pinned.txt                      ← skills protected from accidental deletion
├── skills/                         ← third-party skills (metadata only)
│   ├── find-skills/.source.json
│   ├── skill-creator/.source.json
│   ├── grill-me/.source.json
│   ├── brainstorming/.source.json
│   └── caveman/.source.json
├── my-skills/                      ← my own skills (full content)
│   ├── auto-learner/               ← cron-side: daily_learn.sh, parse_hits.py
│   │   ├── SKILL.md
│   │   └── scripts/
│   ├── auto-scout/                 ← Claude-side: process candidates → digest
│   │   └── SKILL.md
│   ├── show-picks/                 ← /show-picks command
│   │   └── SKILL.md
│   ├── show-installed/             ← /show-installed command
│   │   └── SKILL.md
│   └── harmonyos-multi-module/
│       └── SKILL.md
├── catalog/                        ← discovery queue (auto)
│   ├── candidates.md               ← raw (bash writes)
│   ├── digest.md                   ← curated (Claude writes, ≤ 30 entries)
│   └── digest-archive.md           ← > 90d old (Claude writes)
├── scripts/
│   ├── install.sh                  ← on-demand download + auto-pin
│   ├── clean.sh                    ← remove (refuses if pinned, --force to override)
│   ├── pin.sh                      ← manually pin
│   ├── unpin.sh                    ← unpin (then clean will work)
│   └── full_scan.sh                ← quarterly broad scan
└── docs/
    └── how-to-add-a-skill.md
```

## How it stays small

| Layer | Size on disk |
|---|---|
| This repo (catalog) | **<1MB** (metadata + my 5 skills) |
| `~/.claude/skills/find-skills/` (after install) | ~50KB |
| `~/.claude/skills/grill-me/` (after install) | ~10KB |
| All 5 third-party catalog skills installed at once | **<500KB** |

Compare to: a single 4K video is 1–2GB. Skills are 0.0001% the cost.

## Adding a new skill

See [`docs/how-to-add-a-skill.md`](docs/how-to-add-a-skill.md) for the full SOP. Short version:

1. Wait for Claude to write a structured card to `catalog/digest.md` (待你决定 section)
2. Review the analysis
3. Say "装 X" in chat — Claude runs `install.sh` (auto-pins) and updates `digest.md` + `catalog.md`
4. Commit + push

## Provenance

Built 2026-06-06. Started as a way to stop re-discovering the same 5 skills every other week. Catalog of third-party skills sourced from [skills.sh](https://skills.sh) (the public skills directory). The 50k curator system was added the same day after a `/grill-me` design session.
