#!/usr/bin/env python3
"""Parse GitHub code search JSON from stdin, emit one TSV row per hit:
name<TAB>owner/repo<TAB>path<TAB>stars
"""
import json
import sys

raw = sys.stdin.read()
try:
    d = json.loads(raw)
except json.JSONDecodeError as e:
    print(f"PARSE-ERROR: {e}", file=sys.stderr)
    sys.exit(1)

count = 0
seen_repos = set()
for item in d.get("items", []):
    repo = item.get("repository", {}).get("full_name", "")
    path = item.get("path", "")
    stars = item.get("repository", {}).get("stargazers_count", 0)

    # Use repo's short name (last segment) as the candidate name, so multiple SKILL.md files
    # in the same repo collapse to a single row.
    name = repo.split("/")[-1] if "/" in repo else repo

    # Dedupe per repo (only the first hit per repo makes it through)
    if repo in seen_repos:
        continue
    seen_repos.add(repo)

    print(f"{name}\t{repo}\t{path}\t{stars}")
    count += 1

sys.stderr.write(f"parsed {count} unique repos\n")
