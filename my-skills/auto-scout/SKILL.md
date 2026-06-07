---
name: auto-scout
description: Maintain the user's curated GitHub discovery feed. Reads raw candidates, filters against the user's interest profile, writes structured cards to digest.md, and archives stale entries. Use when starting a new session and the catalog may have new raw entries to process, or when the user mentions digest / candidates / curator / discovery.
type: meta
trigger_keywords:
  - "digest"
  - "candidates"
  - "curator"
  - "discovery"
  - "auto-scout"
  - "github feed"
  - "50k stars"
---

# auto-scout

> The end-to-end pipeline that turns "everything on GitHub" into "what cool-boy2024 should look at next".
> You (the Claude reading this) are part of this pipeline — your job is the **filtering & curation** step.

## The system in one paragraph

Two bash scripts (`scripts/daily_learn.sh` and `scripts/full_scan.sh`) run on cron, fetch raw 50k+ star candidates from GitHub, and append to `catalog/candidates.md`. **You** read that file, filter each entry against the user's interest profile (see `user_interests_profile.md` in the project memory), write structured cards into `catalog/digest.md`, and archive stale entries to `catalog/digest-archive.md`. The user then makes the final call via natural language ("装 X" / "留 X" / "不要 X") or `/show-picks` / `/show-installed`.

## When to run

**At the start of any session that touches this repo** — silently, in the first 30 seconds, before responding to the user. Don't ask "should I process candidates?" — just do it.

**Also** when the user explicitly says things like "看看 digest" / "更新一下" / "今天有什么好货" / invokes `/show-picks`.

## How to process (the 30-second routine)

1. **Read `catalog/candidates.md`** — see what's pending in the raw queue.
2. **Read `catalog/digest.md`** — see what's already curated (avoid duplicates).
3. **For each new raw candidate**:
   - Check it still meets the 50k+ star gate (it's a moving target — stars change).
   - Filter against `user_interests_profile.md` (programming / stocks-crypto-DeFi-finance-quant / English).
   - Write a structured card (template below) into the "待你决定" section of `digest.md`.
   - Drop raw entry from the "pending" awareness (it's now represented in digest).
4. **Archive check**: any entry in digest.md with `**Added**: YYYY-MM-DD` older than 90 days → move to `catalog/digest-archive.md` with a `**[archived YYYY-MM-DD]**` prefix.
5. **Commit + push** with a clear message: `chore: digest update — N new, M archived`.

If candidates.md is empty and digest.md is current, **say nothing** about it. The whole point is to be invisible when there's nothing to do.

## Structured card template

For each entry, use this exact format. Don't deviate — the format *is* the contract with the user.

```markdown
### [project-name](github-url) — ⭐ XXXk
- **类别**: skill | repo | tool | framework
- **一句话**: 干什么的 (≤ 30 字)
- **为什么对你**: 对照兴趣画像的具体用法
- **潜在坑**: 1 个最值得提前知道的问题 (或 "无")
- **建议**: 🟢装 | 🟡看看 | 🔖收藏 | 🔴跳过
- **Tier**: install (≥ 50k) | read (5k–50k)
- **Added**: YYYY-MM-DD
```

Sort newest-first within each section. Keep total entries across all 3 sections ≤ 30.

## Section semantics

| Section | Meaning | What to do when user says "装 X" |
|---|---|---|
| 📥 待你决定 | New, awaiting user's call | Look up type, run install.sh (skill) or mark repo as kept, move to 📦 |
| 📦 已装 | Installed (skill) or kept-as-bookmark (repo) | Update install date + show current usage status |
| 🚫 跳过 | User said "不要" | Move to archive after 90 days; respect their decision |

## "装 X" / "留 X" / "不要 X" — the action protocol

When the user uses natural language:

1. **Parse the verb**:
   - "装 / 装上 / 装好" = install
   - "留 / 收藏 / 收下" = bookmark (for repos) or confirm keep
   - "不要 / 跳过 / 算了" = skip
   - "讲讲 / 说说 / 为什么" = expand the analysis (don't move, just elaborate)
2. **For "装"**:
   - Determine type: is there a SKILL.md in the repo? → skill. Otherwise → repo.
   - **If skill**: confirm intent, then run `./scripts/install.sh <name>` (this auto-pins and downloads to `~/.claude/skills/<name>/`). Update the entry to "📦 已装" with install date.
   - **If repo** (no SKILL.md): no install action. Move to "📦 已装" with a note that it's a repo (bookmarked, not installed). The user can star/clone it themselves.
3. **For "留"**: same as "装" but assumes the user has accepted the recommendation without an install action.
4. **For "不要"**: move to "🚫 跳过" section. Don't delete — it's audit trail.
5. **For "讲讲"**: elaborate the analysis inline. Don't move.

**Always confirm before destructive action** (install, file moves). Format:
> "X 是 skill，要装到 `~/.claude/skills/X/` + auto-pin + 写 .source.json 进 catalog。确认吗？"

## Hard rules — read these before doing anything

- **The 50k+ threshold is for "install" tier only.** See `feedback_discovery_threshold.md` in memory. The 5k–50k "read" tier was added (with user's approval) as a separate path for awareness, not for install. Don't conflate them.
- **Tier mapping in digest.md**:
  - tier=install → 🟢装 (or 🟡看看 if quality is borderline)
  - tier=read → 🔖收藏 (always; never 🟢装 — these don't have the install threshold)
- **Never auto-install without user confirmation.** Even if a candidate has 🟢 recommendation. Always confirm.
- **The user retains final say.** If they say "不要" on something I rated 🟢, fold that into the "I was wrong about this one" model and don't recommend similar again.
- **Don't pad digest.md.** Sparse is fine. 30-entry hard limit (across all 3 sections combined).
- **Commit + push after every update.** This is the user's durable record.

## File map (what lives where)

| File | Owner | Purpose |
|---|---|---|
| `my-skills/auto-learner/scripts/daily_learn.sh` | bash (cron) | Daily: search GitHub with topic, append raw candidates |
| `scripts/full_scan.sh` | bash (cron) | Quarterly: broad search, no topic |
| `catalog/candidates.md` | bash writes, you read | Raw queue, append-only |
| `catalog/digest.md` | **you write** | Curated, ≤ 30 entries, 3 sections |
| `catalog/digest-archive.md` | **you write** | Stale entries, durable record |
| `pinned.txt` | install.sh writes | Skills protected from accidental deletion |
| `skills/<name>/.source.json` | user / install.sh reads | Per-skill install metadata |

## Related skills (in this catalog)

- `find-skills` (catalog metadata) — broader discovery, can supplement raw candidates
- `skill-creator` (catalog metadata) — if the user asks "can I make a skill that does X", use this
- `grill-me` (already installed) — for stress-testing new designs
