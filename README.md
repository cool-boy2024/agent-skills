# agent-skills

> A lightweight **catalog** of agent skills. The repo stays under 1MB by storing only metadata for third-party skills; real content is downloaded on demand via `scripts/install.sh`.

This is **cool-boy2024**'s personal skill library. Two goals:
1. **Find** good skills fast (search skills.sh, GitHub, npm) — entry point: `find-skills`
2. **Curate** what I actually keep — entry point: `auto-learner`

## Quick start

```bash
# See what's in the catalog
./scripts/install.sh              # no args → list

# Install a skill globally (pulls to ~/.claude/skills/)
./scripts/install.sh find-skills
./scripts/install.sh grill-me
./scripts/install.sh caveman

# Remove when done
./scripts/clean.sh caveman

# Daily discovery routine (cron-friendly)
./my-skills/auto-learner/scripts/daily_learn.sh "rust async runtime"
```

## Layout

```
agent-skills/
├── README.md                       ← you are here
├── catalog.md                      ← curated index of all skills
├── skills/                         ← third-party skills (metadata only)
│   ├── find-skills/.source.json    ← owner/repo/path/install_cmd
│   ├── skill-creator/.source.json
│   ├── grill-me/.source.json
│   ├── brainstorming/.source.json
│   └── caveman/.source.json
├── my-skills/                      ← my own skills (full content)
│   ├── auto-learner/
│   │   ├── SKILL.md
│   │   └── scripts/daily_learn.sh
│   └── harmonyos-multi-module/
│       └── SKILL.md
├── catalog/                        ← append-only discovery queue
│   └── candidates.md
├── scripts/
│   ├── install.sh                  ← on-demand download
│   └── clean.sh                    ← remove
└── docs/
    └── how-to-add-a-skill.md
```

## How it stays small

| Layer | Size on disk |
|---|---|
| This repo (catalog) | **<1MB** (metadata + my 2 skills) |
| `~/.claude/skills/find-skills/` (after install) | ~50KB |
| `~/.claude/skills/grill-me/` (after install) | ~10KB |
| All 5 catalog skills installed at once | **<500KB** |

Compare to: a single 4K video is 1–2GB. Skills are 0.0001% the cost.

## The catalog philosophy

A skill earns a slot here only if it passes all three gates (see `catalog.md`):

1. **Active maintenance** (last commit ≤ 6 months)
2. **Clear scope** (one SKILL.md, one job)
3. **Proven adoption** (≥50K installs or ≥1K stars) **OR** a problem I hit ≥2 times

Stars and installs are a useful but imperfect signal. The `auto-learner` skill automates the discovery + gate-checking; humans make the final call.

## Adding a new skill

See [`docs/how-to-add-a-skill.md`](docs/how-to-add-a-skill.md) for the full SOP. Short version:

1. Run `./scripts/install.sh <new-skill>` to test
2. If you keep using it for a week, add a `.source.json` under `skills/<name>/`
3. Update `catalog.md` with one row
4. Commit & push

## Provenance

Built 2026-06-06. Started as a way to stop re-discovering the same 5 skills every other week. Catalog of third-party skills sourced from [skills.sh](https://skills.sh) (the public skills directory).
