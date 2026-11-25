# Review brief: Studio application architecture research

Shared brief for every review agent. You review ONE research file, named in your dispatch. Read `_brief.md` first: the research agent worked from it.

## What to check

1. **Factual accuracy (most important).** Re-verify live, today 2026-11-25, every load-bearing claim: Electron APIs and their behaviour in Electron 45, library versions and maintenance status, performance numbers, security defaults. Fetch the cited source. Does it say what the file claims? Is it current? Does a newer source contradict it? Check local-code citations (`src/`, `/Users/daniel/Work/expause/expause_web`, `/Users/daniel/Work/devscene`) against the files.
2. **Citations.** Look for uncited non-obvious claims, dead links, secondary sources used where a primary one exists, and [verified]/[secondary]/[inferred] tags that overstate.
3. **Coverage against the brief.** Owner questions the area should answer but doesn't; sub-topics in the area's row skipped.
4. **Reasoning and proportion.** Conclusions that don't follow from the evidence; missed counter-evidence; generic best practice that ignores this app (small board app, process- and file-driven, live state, browser mode, the harness layer map, the security bar). Flag over-engineering as firmly as gaps: a pattern or library whose cost exceeds its payoff at this size is a finding.
5. **Consistency.** Recommendations that contradict `../product-startup-research/10-recommendation.md` or the security bar without saying so and why.
6. **Scope.** Content that repeats another area file at length (a short cross-reference is fine).

## Output

Write to `reviews/<the reviewed file's name>`:

```
# Review — <file>
> Reviewer verdict: PASS | PASS WITH FIXES | FAIL · Date: 2026-11-25

## Summary            (3–6 lines)
## Must fix           (wrong facts, misleading conclusions, missing required coverage)
## Should fix         (weak citations, overstated confidence, gaps, over-engineering)
## Nice to have
```

Number each finding (M1, S1, N1 …). Each gives the location (section or quote), the problem, the evidence (a URL or path you checked), and the concrete fix (corrected text where possible). Don't edit the research file. Return a summary of 10 lines or fewer with your verdict and finding counts.
