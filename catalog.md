# Skills Catalog

> Personal curation of agent skills. The repo itself stays light (<1MB) by only storing **metadata**; actual skill content is downloaded on demand via `scripts/install.sh`.

## How this catalog works

| Concept | Where it lives |
|---|---|
| **Catalog** (this repo) | Metadata, links, my own skills. Always on GitHub. |
| **Active skills** (in use) | `~/.claude/skills/<name>/` — pulled on demand |
| **Install method** | `npx skills add <owner/repo>` (preferred) or `gh repo clone` for repos that don't ship on npm |

To install a skill: `./scripts/install.sh <skill-name>`
To remove: `./scripts/clean.sh <skill-name>`

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

### 🛠️ My own (stored as full content, not metadata)
| Skill | Source | Purpose |
|---|---|---|
| **auto-learner** | `my-skills/auto-learner/` | Daily routine: discover + evaluate new skills from the ecosystem. |
| **harmonyos-multi-module** | `my-skills/harmonyos-multi-module/` | Lessons from real HarmonyOS NEXT multi-module refactors (HAR, HAP, HSP, ohpm, hvigor). |

## How a skill gets added to this catalog

A skill earns a slot here if it passes all three gates:

1. **Active maintenance** — last commit within 6 months
2. **Clear scope** — single responsibility, fits in one SKILL.md
3. **Either**:
   - **Proven**: >50K installs on skills.sh **OR** >1K GitHub stars
   - **Personal need**: I (cool-boy2024) hit a recurring problem it solves

See `docs/how-to-add-a-skill.md` for the full procedure, including how to use `auto-learner` to find candidates automatically.

## Current counts

- **Catalog entries**: 7 (5 third-party + 2 self-authored)
- **Last curated**: 2026-06-06
- **Storage used by catalog itself**: <1MB
