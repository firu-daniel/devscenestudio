# Review brief — product-startup research

Shared brief for every review agent. You review ONE research file, which your dispatch names. Read `_brief.md` first: it is the brief the research agent worked from.

## What to check

1. **Factual accuracy (most important).** Re-verify live, today 2026-11-12, every load-bearing claim: versions, release dates, deprecation or support status, licence terms, prices, benchmark numbers, platform support and API capabilities. Fetch the cited source. Does it say what the file claims? Is it current? Is there a newer source that contradicts it?
2. **Citations.** Look for uncited non-obvious claims, dead links, a secondary source used where a primary one exists, and confidence tags ([verified]/[secondary]/[inferred]) that overstate.
3. **Coverage against the brief.** Look for candidates the brief names that are missing, owner questions the area should answer that are unanswered, and sub-topics the dispatch asked for that are skipped.
4. **Reasoning.** Look for conclusions that don't follow from the evidence, missed counter-evidence, and generic advice that ignores this app's specifics: small board app, process/file driven, Windows via WSL2 only, Node/TS harness CLI, no app stores.
5. **Scope.** Flag content that duplicates another area file (01–05) at length, though a short cross-reference is fine.

## Output

Write to `reviews/<same filename as the reviewed file>`:

```
# Review — <file>
> Reviewer verdict: PASS | PASS WITH FIXES | FAIL · Date: 2026-11-12

## Summary            (3–6 lines)
## Must fix           (wrong facts, misleading conclusions, missing required coverage)
## Should fix         (weak citations, overstated confidence, gaps)
## Nice to have
```

Number each finding (M1, S1, N1 …). Each finding gives: the location (section or quote), the problem, the evidence (a URL you checked), and the concrete fix (the corrected text where possible). Don't edit the research file yourself. Return a ≤ 10-line summary with your verdict and finding counts.
