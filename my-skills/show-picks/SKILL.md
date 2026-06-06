---
name: show-picks
description: Read catalog/digest.md "待你决定" section and present it to the user as a quick-scan pick list. Use when the user asks "今天有什么好货" / "show me picks" / "what's new" / invokes /show-picks, or when auto-scout has just updated digest.md and the user wants to see what's pending.
type: interface
trigger_keywords:
  - "show picks"
  - "show-picks"
  - "today's picks"
  - "what's new"
  - "今天有什么好货"
  - "看看 digest"
  - "待你决定"
---

# show-picks

> The on-demand entry point into the curator's queue.

## What this does

Reads `catalog/digest.md` in this repo, extracts the **📥 待你决定** section, and presents it to the user as a numbered list with quick-decision shortcuts.

The goal is **scan-in-30-seconds**: the user should be able to look at the output and say "装 1, 2; 不要 3" in one breath.

## How to run

1. Read `catalog/digest.md` (it's in the repo root: `agent-skills/catalog/digest.md`).
2. Extract everything under `## 📥 待你决定 (awaiting your call)`.
3. Format each entry as a numbered pick. Use the existing structured card fields.
4. End with a one-line "what to say" prompt: `回复 "装 1, 3" 或 "留 2" 或 "不要 4" 我就动了`

## Output format

```
📥 digest.md "待你决定" 共 N 条

1. [project-name](url) ⭐ XXXk
   类别: skill | repo | tool
   一句话: ...
   为什么对你: ...
   潜在坑: ...
   建议: 🟢装 / 🟡看看 / 🔴跳过

2. ...

回复 "装 1, 3" 或 "留 2" 或 "不要 4" 我就动了
```

If the section is empty, say so directly:
> "待你决定 0 条。要么最近没新候选通过 50k 门槛，要么你之前全清过了。下次 /show-installed 看装好的状态。"

## Companion actions

- `/show-installed` — the audit view, opposite direction
- "讲讲 1" — expand a specific pick's analysis (don't move, just elaborate)
- "装 X" / "留 X" / "不要 X" — direct action, no need to invoke this skill

## Files

- `SKILL.md` — this file
- Reads from: `../../catalog/digest.md`
- Optional: if `catalog/digest.md` is empty, fall back to the `auto-scout` skill to process `catalog/candidates.md` first.
