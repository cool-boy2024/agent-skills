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

### [superpowers](https://github.com/obra/superpowers) — ⭐ 220k 🔥
- **类别**: framework (14 个 sub-skills)
- **一句话**: 完整 agentic skills 框架 + 软件开发方法论。**就是今晚给我看的那个 219k 那个**
- **为什么对你**: 你**已经装了 `brainstorming`（1/14）**——这同一仓库。装 superpowers = 一次拿全剩下 13 个方法论 skill：`dispatching-parallel-agents` / `executing-plans` / `systematic-debugging` / `test-driven-development` / `verification-before-completion` / `writing-plans` / `writing-skills` 等。对**编程**（任何 dev 工作，包括你的 web3 智能合约）价值高
- **潜在坑**: 14 个 skill 一次装会**显著改变 Claude 的行为**（这套方法论强调"先 brainstorm / 先 TDD / verification before completion"等）。你"另一个我"现在很自由，**装 superpowers 会引入一套 OS**。要装就得接受"它会反过来管 Claude 的工作流"
- **建议**: 🟢装（tier=install；你 50k+ 硬指标合格，框架 220k star 是真大牌；但**装前先读 README 知道这 14 个分别干什么**——决定权在你）
- **Tier**: install
- **Added**: 2026-06-07

### [prompt-master](https://github.com/nidhinjs/prompt-master) — ⭐ 9k
- **类别**: skill
- **一句话**: 为任意 AI 工具生成"零 token 浪费"的高质量 prompt
- **为什么对你**: 你跟 Claude / AI 工具打交道多，但目前你是 casual 用户，**这个 skill 更适合"重度 prompt engineer"**。收藏看你以后是不是往那个方向走
- **潜在坑**: 立场偏强（SKILL.md 里硬规则一堆，比如"不要加 CoT 给 reasoning-native 模型"），跟你"另一个我"想要的"自由判断"可能略冲突
- **建议**: 🟡看看（tier=read，跟你画像契合度中等；先看 SKILL.md 再决定要不要收藏）
- **Tier**: read
- **Added**: 2026-06-07

### [dev-browser](https://github.com/SawyerHood/dev-browser) — ⭐ 6.2k
- **类别**: skill
- **一句话**: Claude 浏览器自动化，persistent page state 跨多次调用保留
- **为什么对你**: 跟 web-access **直接竞品**。星略少（6.2k vs 7.3k），但 npm 包形式分发 + 本地 daemon 维护状态，可能体验更顺。**作 web-access 的备胎留着**——半年后哪个还活着用哪个
- **潜在坑**: 2 days ago 极活跃（在维护），但 TS 生态变动快；需要全局 `npm install -g dev-browser` 再 `dev-browser install`，比 web-access 多一步
- **建议**: 🔖收藏（tier=read；你说"经常用"web-access，留个备胎）
- **Tier**: read
- **Added**: 2026-06-07

## 📦 已装 (installed / kept)

### [web-access](https://github.com/eze-is/web-access) — ⭐ 7.3k
- **类别**: skill
- **一句话**: 给 Claude Code 联网能力（CDP 浏览器 + 抓取 + 登录后操作）
- **为什么对你**: 补 Claude Code 的联网短板
- **建议**: 🟢已装
- **Tier**: install
- **Installed**: 2026-06-07
- **Use when**: 任何需要 Claude 联网的活（搜索、抓页、查 GitHub、登录后操作）

## 🚫 跳过 (passed on)

<!-- You said "不要" — kept here for reference; auto-archives after 90 days. -->

_(empty)_
