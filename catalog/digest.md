# Curated Digest

> Claude-maintained, interest-profile-filtered view of `catalog/candidates.md`.
>
> **This file is auto-updated** — every time you start a Claude session, the assistant will:
> 1. Read raw candidates from `catalog/candidates.md`
> 2. Filter against your interest profile (programming / finance-DeFi-quant / English)
> 3. Write structured cards here
> 4. Archive entries > 90 days old to `catalog/digest-archive.md`
> 5. Commit + push
>
> **Tier system** (per `feedback_discovery_threshold.md` + the 2026-06-06 `/grill-me` decision):
> - **install** (≥ 50k stars) → action verb 🟢装 (will actually `install.sh` + auto-pin)
> - **read** (5k–50k stars) → action verb 🔖收藏 (just bookmark, no install)
> - 5k star hard floor; below is dropped
>
> **Hard limits**:
> - Main file holds ≤ 30 entries total (across all 3 sections)
> - 50k+ install threshold is **non-negotiable** (no second-tier install)
>
> **How to use**:
> - See the suggestion under each card and tell me "装 X" / "留 X" / "不要 X"
> - Or invoke `/show-picks` for a quick re-read, `/show-installed` for the audit view

## 📥 待你决定 (awaiting your call)

### [web-access](https://github.com/eze-is/web-access) — ⭐ 7.3k
- **类别**: skill
- **一句话**: 给 Claude Code 装上完整联网能力（CDP 浏览器 + 抓取 + 登录后操作）
- **为什么对你**: 你的很多 coding 工作（catalog 系统、GitHub API 查询）都受限于 Claude 的"不能联网"。这个 skill 直接补这块。对**编程**兴趣中上
- **潜在坑**: README 警告"部分站点对浏览器自动化操作检测严格，存在账号封禁风险" —— 用之前心理有数
- **建议**: 🔖收藏（tier=read，不会自动 install）
- **Tier**: read
- **Added**: 2026-06-07

### [prompt-master](https://github.com/nidhinjs/prompt-master) — ⭐ 9k
- **类别**: skill
- **一句话**: 为任意 AI 工具生成"零 token 浪费"的高质量 prompt
- **为什么对你**: 你跟 Claude / AI 工具打交道多，但目前你是 casual 用户，**这个 skill 更适合"重度 prompt engineer"**。收藏看你以后是不是往那个方向走
- **潜在坑**: 立场偏强（SKILL.md 里硬规则一堆，比如"不要加 CoT 给 reasoning-native 模型"），跟你"另一个我"想要的"自由判断"可能略冲突
- **建议**: 🟡看看（tier=read，跟你画像契合度中等；先看 SKILL.md 再决定要不要收藏）
- **Tier**: read
- **Added**: 2026-06-07

## 📦 已装 (installed / kept)

<!-- Entries that earned a slot. For skills: install.sh ran + auto-pinned. For repos: bookmarked, no install. -->

_(empty — say "装 X" to promote from 待你决定)_

## 🚫 跳过 (passed on)

<!-- You said "不要" — kept here for reference; auto-archives after 90 days. -->

_(empty)_
