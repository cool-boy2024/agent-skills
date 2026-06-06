# How to add a skill to this catalog

A 4-step SOP. Goal: catalog stays small, every entry earns its slot, nothing is duplicated.

## Step 1: Discover

Find candidates via any of:

```bash
# Search skills.sh (interactive)
npx skills find "rust async"

# Search GitHub for SKILL.md files
gh search code "filename:SKILL.md language:markdown <topic>"

# Ask Claude to use find-skills
# (in a Claude session with find-skills installed)
```

A good first-cut candidate has:
- Clear one-line description ("does X, when Y")
- ≤200 lines in SKILL.md
- Active repo (commit in last 6 months)

## Step 2: Test (no commitment)

Install it locally and use it for a real task:

```bash
./scripts/install.sh <candidate>
# use it for ~3-5 real tasks over a week
```

If you don't reach for it after a week, drop it. The bar for catalog membership is "I would notice if it disappeared."

## Step 3: Stress-test (only for borderline cases)

If installs are <50K and it's not a personal-needs fit, run it through `grill-me`:

```bash
./scripts/install.sh grill-me
```

Then in Claude, ask: "grill-me this SKILL.md and tell me whether it earns a catalog slot."

Apply the 6 gates from `my-skills/auto-learner/SKILL.md`:

1. Active maintenance (last commit ≤ 6 months)
2. Single responsibility
3. Adoption signal (≥50K installs or ≥1K stars)
4. License is MIT/Apache/BSD/public
5. Real content (SKILL.md present, not a stub)
6. Either proven adoption OR personal fit

## Step 4: Commit to catalog

1. **Create the metadata file**: `skills/<name>/.source.json`. Use one of the existing entries as a template.
2. **Update the catalog**: add a one-line row to `catalog.md` in the right category.
3. **Update counts**: bump "Last curated" date and the entry count.
4. **Commit & push**:

```bash
git add skills/<name>/ catalog.md
git commit -m "Add <name> to catalog: <one-line why>"
git push
```

5. (Optional) Schedule `auto-learner` to surface similar candidates in the future — see the cron snippet in `my-skills/auto-learner/SKILL.md`.

## When to remove a skill

- Repo hasn't been touched in 18+ months
- You stopped reaching for it
- It got superseded by something strictly better
- License changed to GPL/AGPL/SSPL

To remove: delete `skills/<name>/`, remove the row from `catalog.md`, commit.
