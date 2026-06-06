---
name: show-installed
description: Audit view of the user's installed skills / kept repos. Reads catalog/digest.md "已装" section and pinned.txt, presents status (install date, age, type, last-referenced). Use when the user asks "我装了什么" / "audit catalog" / "review installed" / invokes /show-installed.
type: interface
trigger_keywords:
  - "show installed"
  - "show-installed"
  - "我装了什么"
  - "audit"
  - "review installed"
  - "已装"
  - "catalog 状态"
---

# show-installed

> The audit view. Use when the user wants to step back and ask "what do I actually have, and is it still earning its keep?"

## What this does

Reads two sources:

1. `catalog/digest.md` **📦 已装** section — every entry Claude has ever curated as "kept"
2. `pinned.txt` — the auto-pinned skills from `install.sh`

For each, presents a compact status row: name, type, install date, age, any 1-line note.

The goal: help the user spot **stale installs** — things they installed 6+ months ago that might be safe to unpin + clean.

## How to run

1. Read `catalog/digest.md` — extract `## 📦 已装` section.
2. Read `pinned.txt` — get the raw pinned name list.
3. Cross-reference: any name in pinned.txt that doesn't appear in digest.md "📦 已装" is a **gap** (a pinned skill that was never recorded in digest — usually because it was installed before digest existed). Flag it.
4. Sort by install date (oldest first, so stale items surface at the top).
5. Compute "age" as `today - install_date` in days/months.
6. Flag any entry with age > 180 days as 🟡 (worth a look) — the user can decide to keep or unpin+clean.

## Output format

```
📦 你装好的共 N 个 (M 个 skill, K 个 repo 书签)

🟡 > 180 天没动的:

  • skill-name (skill, 装于 YYYY-MM-DD, 距今 N 天)
    备注: 当时为什么装: ...
  • ...

✅ 近期 (< 180 天):

  • skill-name (skill, 装于 YYYY-MM-DD)
  • ...

📌 pinned.txt 里但 digest 没记录的 (gap):
  • orphan-skill-name
  • ...

要不要清理?
  "清掉 X" → 我跑 unpin.sh X && clean.sh X
  "保留" → 不动
```

## Action protocol

- "清掉 X" / "移除 X" / "不要 X" (when X is in 已装) → run `./scripts/unpin.sh X && ./scripts/clean.sh X`. Move X to "🚫 跳过" in digest.md first.
- "保留" / "不动" → do nothing.
- "全部留着" / "都留着" → no action, just acknowledge.

**Never run clean.sh with --force without explicit user instruction.** Default respect for the pin mechanism.

## Files

- `SKILL.md` — this file
- Reads from: `../../catalog/digest.md`, `../../pinned.txt`
- Mutates (on user action): `../../catalog/digest.md`, `../../pinned.txt`, plus calls `./scripts/unpin.sh`, `./scripts/clean.sh`
