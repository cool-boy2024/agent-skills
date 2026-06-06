---
name: auto-learner
description: Daily routine for discovering, evaluating, and curating new agent skills from the open ecosystem. Combines find-skills (discovery) + grill-me (stress-test) + skill-creator (audit) to keep the catalog fresh. Use when asked "what new skills are out there?", "should I add X to my catalog?", or when the user wants to schedule daily learning.
type: meta
trigger_keywords:
  - "find new skills"
  - "what skills exist for"
  - "should I add"
  - "daily learning"
  - "auto learner"
  - "skill recommendations"
---

# auto-learner

> Curate the catalog automatically. Discover → evaluate → propose. The human decides.

## What this skill does

Runs a 3-stage pipeline against the open skill ecosystem:

1. **Discover** — `npx skills find "<topic>"` returns candidate skills from skills.sh
2. **Stress-test** — for each candidate, apply the `grill-me` framework (decision criteria below)
3. **Propose** — write a 1-line entry into `catalog/candidates.md` for the human to review

It does **not** auto-install. The human approves before anything enters the catalog.

## How to use this skill

### Manual run

```bash
./my-skills/auto-learner/scripts/daily_learn.sh "topic here"
```

Example:
```bash
./my-skills/auto-learner/scripts/daily_learn.sh "rust cli"
```

This will:
1. Search skills.sh for skills matching the topic
2. For each result, score it against the gates (see below)
3. Append surviving candidates to `catalog/candidates.md` with a one-line reason

### Daily scheduled run (the "24-hour learning" idea)

This is a Claude Code / cron combination. Claude can't run by itself, but you can schedule the **script** to run daily and **present a digest to you** when you next open Claude.

```bash
# Run every day at 9 AM local time
0 9 * * * cd /path/to/agent-skills && ./my-skills/auto-learner/scripts/daily_learn.sh "any topic" >> /tmp/auto-learner.log 2>&1
```

Then in your morning Claude session, ask:
> "Read /tmp/auto-learner.log and tell me what new skills are worth considering."

The script + Claude reviewing the output is the closest practical answer to "24/7 learning" without burning API tokens on idle polling.

## Decision gates (the "is this a good skill?" criteria)

A candidate skill is added to `catalog/candidates.md` only if it passes **all** of:

| Gate | Threshold | Why |
|---|---|---|
| Active maintenance | Last commit ≤ 6 months | Stale skills lie about working behavior |
| Single responsibility | Fits in one SKILL.md | Multi-purpose skills are hard to evaluate |
| Adoption signal | ≥50K installs **or** ≥1K GH stars | Crowdsourced validation |
| **OR** personal fit | Solves a problem I (the user) hit ≥2 times | Personal track record beats stars |
| No license trap | License is MIT / Apache-2.0 / BSD / public | Avoid GPL/AGPL for personal use |
| Real content | Has SKILL.md, not just a stub | Empty wrapper = no value |

The **`grill-me` skill** is the actual stress-test prompt to apply to borderline cases. Load it via:
```bash
./scripts/install.sh grill-me
```

Then in a Claude session, paste the candidate's SKILL.md and say: "grill-me this — does it earn a slot in my catalog?"

## Why "good skill" is itself a learned judgment

These gates came from reverse-engineering the top 50 skills on skills.sh and asking **what they have in common**:

- Tight frontmatter (YAML name/description)
- Description that says **what + when**, not just **what**
- Triggers / examples, not abstract prose
- Self-contained (one folder, one SKILL.md unless there are heavy references)
- Maintained within last 6 months
- Either proven by adoption or proven by your own need

A "great" skill has all six. A "good" skill has 4-5. A "no" has 3 or fewer.

## Files

- `SKILL.md` — this file
- `scripts/daily_learn.sh` — the runner
- `catalog/candidates.md` — append-only queue of suggestions waiting for human review
