---
name: harmonyos-multi-module
description: Hard-won rules for HarmonyOS NEXT multi-module projects (Stage model, ArkTS 1.1 strict, V2 decorators). Use when building, refactoring, or debugging a project with HAR / HAP / HSP modules — especially when hitting "module.json5 not found", "Invalid main file", "$r resource not found", or "Failed to resolve OhmUrl" errors.
type: project
triggers:
  - "harmonyos"
  - "鸿蒙"
  - "Stage model"
  - "HAR"
  - "HAP"
  - "HSP"
  - "ohpm"
  - "hvigor"
  - "$r resource not found"
  - "OhmUrl"
  - "build-profile.json5"
---

# harmonyos-multi-module

> Eight rules that took 8 commits to learn. Read these BEFORE you start the next refactor.

This skill encodes the non-obvious rules of HarmonyOS NEXT multi-module development. Each rule below was discovered the hard way (a failed build), then verified against `hvigor-ohos-plugin` source.

---

## The 8 rules

### 1. `$r()` resolves to the **calling module's** resources only

In a `.ets` file, `Image($r('app.media.bg_hotel_full.jpg'))` looks for that resource in the **module that owns the .ets file**, NOT in any module listed under `oh-package.json5` dependencies.

- Cross-module `$r` fails **silently** (compile error, no helpful message).
- Workarounds:
  - Copy the resource into each consuming module under the same filename
  - Or use `@Param bg: Resource | null = null` and let the caller inject

### 2. `hvigorfile.ts` system task must match the module type

| File location | Required `system` value |
|---|---|
| `<projectRoot>/hvigorfile.ts` | `appTasks` |
| `<moduleRoot>/hvigorfile.ts` (HAP) | `hapTasks` |
| `<moduleRoot>/hvigorfile.ts` (HAR) | `harTasks` |
| `<moduleRoot>/hvigorfile.ts` (HSP) | `hspTasks` |

Wrong choice produces a misleading error: *"The project-level build-profile.json5 file does not comply with the schema"* — but the actual fix is in `hvigorfile.ts`, not the build profile.

### 3. Stage-mode HARs need `src/main/module.json5` + `targets`

A HAR is not exempt from `module.json5`. Required:

```json5
// src/main/module.json5
{
  module: {
    name: "commons",
    type: "har",
    deviceTypes: ["phone", "tablet"]
  }
}
```

```json5
// build-profile.json5
{
  buildOption: {},
  targets: [{ name: "default" }]   // minItems: 1, do NOT omit
}
```

The "module.json5 file not found" error message blames the wrong file — the real cause is the HAR plugin needing its target declared.

### 4. `oh-package.json5` `main` is relative to the **module root**

If your barrel is at `<module>/src/main/ets/Index.ets`:

```json5
{
  main: "src/main/ets/Index.ets"     // NOT "Index.ets"
}
```

The template's convention (barrel at module root with `main: "Index.ets"`) is also fine, but requires re-rooting all relative imports inside the barrel.

### 5. Local module deps MUST use the `file:` scheme as a string

```json5
// ✅ right
{ "dependencies": { "commons": "file:../../commons" } }

// ❌ wrong (causes ohpm error 00640001 "p.includes is not a function")
{ "dependencies": { "commons": {} } }
```

The `{}` form leaves `spec` undefined; ohpm then calls `.includes("file:")` on undefined → TypeError.

### 6. `AppScope/` is auto-detected, never configure it

Don't add `appScope: "../AppScope"` to a HAP's `build-profile.json5`. The HAP schema doesn't allow it, and hvigor auto-detects `<projectRoot>/AppScope/` from the project structure.

### 7. Cross-module imports use the **module name**, not internal paths

```ts
// ✅ right
import { SceneMode } from 'home';

// ❌ wrong (error 10311002 "Failed to resolve OhmUrl")
import { SceneMode } from 'home/model/HomeState';
```

HarmonyOS uses `OhmUrl` resolution keyed by `oh-package.json5`'s `name`. If the symbol isn't re-exported from `<module>/src/main/ets/Index.ets`, add it there — that's the module's only public contract.

### 8. Features coordinate via **hook callbacks** wired in the product layer

HARs must not import each other (one-way deps: `features → commons`, never `feature → feature`). Cross-feature wiring lives in the product HAP:

- Add `setXxxHook(callback)` to the source VM
- Invoke the hook inside the source VM's action method
- Wire each hook in the product layer's `MainTabsPage.aboutToAppear`

For complex enum mapping (e.g. `SceneMode.BRIGHT → LightSceneMode.LEISURE`), do the switch in the product layer, not in either VM.

---

## Reference project shape (a working example)

```
MyProject/
├── AppScope/                  # auto-detected
│   ├── app.json5
│   └── resources/
├── commons/                   # HAR: components/constants/state/theme/utils
│   ├── src/main/
│   │   ├── module.json5       # type: "har"
│   │   └── ets/Index.ets      # barrel
│   ├── build-profile.json5    # targets: [{name: "default"}]
│   └── oh-package.json5
├── features/
│   ├── login/                 # HAR
│   ├── home/                  # HAR
│   └── light/                 # HAR
├── products/
│   └── phone/                 # HAP
│       └── src/main/ets/
│           ├── entryability/
│           ├── pages/
│           └── product/MainTabsPage.ets   # wires cross-feature hooks here
├── hvigorfile.ts              # system: appTasks
├── build-profile.json5        # registers all modules + AppScope
└── oh-package.json5
```

---

## When to use this skill

- Starting any new HarmonyOS NEXT project that will have >1 module
- Hitting the 5 specific error messages listed in the trigger keywords
- Refactoring a single-module `entry/` HAP into `features/*` + `products/*`
- Auditing an existing project against the 8 rules

## When NOT to use this skill

- Single-module HarmonyOS projects (no benefit, just noise)
- HarmonyOS 4.x or earlier (different model: FA, not Stage; `$r` rules are different)
- Non-HarmonyOS ArkTS projects (OpenHarmony distro differences may apply)

---

## Provenance

Rules extracted from a real refactor of a 智慧客房 (smart-hotel-room) project on 2026-06-04, across 8 incremental commits. Verified against `hvigor-ohos-plugin` source in:
- `plugin/common/abstract-module-plugin.js` (rule 3)
- `plugin/strategy/stage-init-strategy.js` (rule 3)
- `ohos-har-module-build-profile-schema.json` (rule 3)
- ohpm `AsyncGraphBuilder.addChildBuildTask` (rule 5)

Reference template: DevEco Studio's "Flexible Layout Ability" at `/Applications/DevEco-Studio.app/Contents/plugins/openharmony/lib/templates/ability/Flexible Layout Ability/`.
