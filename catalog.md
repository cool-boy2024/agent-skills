# Skills Catalog

> Personal curation of agent skills. The repo itself stays light (<1MB) by only storing **metadata**; actual skill content is downloaded on demand via `scripts/install.sh`.
>
> This file is the **browsable index** — what we have, organized by category. The **internal working queue** (待你决定 / 已装 / 跳过) lives in `catalog/digest.md` and is auto-maintained by Claude.

## How this catalog works

| Layer | Where | Maintained by | Purpose |
|---|---|---|---|
| **Catalog** (this file) | `catalog.md` | hand-curated | Browsable index for humans |
| **Raw candidates** | `catalog/candidates.md` | bash (cron) | Append-only queue from GitHub search |
| **Curated digest** | `catalog/digest.md` | Claude (every session) | Interest-filtered, ≤ 30 entries, 3 sections |
| **Active skills** | `~/.claude/skills/<name>/` | install.sh | Pulled on demand |
| **Pinned list** | `pinned.txt` | install.sh (auto) | Skills protected from accidental deletion |

To install: `./scripts/install.sh <skill-name>`
To remove: `./scripts/unpin.sh <name> && ./scripts/clean.sh <name>`

## Discovery pipeline (the 50k curator system)

1. **cron daily** (`scripts/daily_learn.sh`): searches GitHub for `SKILL.md` files matching a topic, gates on **≥ 50,000 stars** + active + non-archived. Appends survivors to `catalog/candidates.md`.
2. **cron quarterly** (`scripts/full_scan.sh`): same but **no topic filter** — catches old-but-still-great projects the daily sweep misses.
3. **Claude, every session**: reads `candidates.md`, filters against the user's interest profile (programming / stocks-crypto-DeFi-finance-quant / English), writes structured cards into `digest.md`. Archives > 90-day-old entries to `digest-archive.md`.
4. **User**: sees `digest.md` via `/show-picks` or just by chatting. Says "装 X" / "留 Y" / "不要 Z". Claude acts.

The 50k+ star threshold is **single bar, no second tier** (see `feedback_discovery_threshold.md` in memory). Lower-star skills are not added to digest under any framing.

## Categories

### 🔍 Discovery — find new skills
| Skill | Source | Installs | Why it's here |
|---|---|---|---|
| **find-skills** | vercel-labs/skills | 1.9M | The #1 ranked skill. Searches the open ecosystem. The entry point for everything else. |

### 🧠 Meta — how to think about skills
| Skill | Source | Installs | Why it's here |
|---|---|---|---|
| **skill-creator** | anthropics/skills | 254K | Official spec for what makes a *good* skill (SKILL.md format, progressive disclosure). |
| **brainstorming** | obra/superpowers | 204K | Don't jump to solutions. Surface hidden requirements first. |
| **grill-me** | mattpocock/skills | 267K | Pre-commit stress test. Relentlessly questions the design. |

### ⚡ Efficiency — output quality
| Skill | Source | Installs | Why it's here |
|---|---|---|---|
| **caveman** | juliusbrussee/caveman | 216K | Cut 75% of output tokens. Useful when budget is tight. |

### 🤖 Auto-scout — pipeline orchestration
| Skill | Source | Purpose |
|---|---|---|
| **auto-learner** | `my-skills/auto-learner/` | The cron scripts (daily_learn.sh, full_scan.sh). Bash side of the pipeline. |
| **auto-scout** | `my-skills/auto-scout/` | The Claude-side skill: process candidates.md → digest.md. |
| **show-picks** | `my-skills/show-picks/` | On-demand: "今天有什么好货?" → presents digest 待你决定. |
| **show-installed** | `my-skills/show-installed/` | On-demand: audit view of 已装 + status. |

### 🛠️ My own (stored as full content, not metadata)
| Skill | Source | Purpose |
|---|---|---|
| **harmonyos-multi-module** | `my-skills/harmonyos-multi-module/` | Lessons from real HarmonyOS NEXT multi-module refactors (HAR, HAP, HSP, ohpm, hvigor). |

## How a skill gets added to this catalog

1. Cron (daily or quarterly) writes a raw entry to `catalog/candidates.md`.
2. Next session, Claude filters it against the interest profile and writes a structured card to `digest.md` (待你决定 section).
3. User says "装 X" or "留 X" → Claude runs `install.sh` (for skills) or just marks as kept (for repos).
4. Claude updates `catalog.md` (this file) with the new entry under the appropriate category.
5. Commit + push.

The reverse (removing a skill) is gated by the pin mechanism: `unpin.sh` then `clean.sh` is the safe two-step. `--force` skips the gate.

## Current counts

- **Catalog entries**: 5 third-party (find-skills, skill-creator, brainstorming, grill-me, caveman) + 4 self-authored (auto-learner, auto-scout, show-picks, show-installed) + 1 legacy (harmonyos-multi-module) = 10
- **Discovery threshold**: 50,000 GitHub stars
- **Last curated**: 2026-06-06
- **Storage used by catalog itself**: <1MB
