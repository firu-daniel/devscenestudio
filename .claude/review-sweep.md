# The review sweep

> **Read this when:** you are the end-of-branch reviewer running the deterministic sweep over a branch's added lines, or the analyze pass filling this document from the repository's own code. **Skip when:** you are a per-unit implementer or reviewer; neither loads this file.

**Purpose.** The escape classes this project's end-of-branch review sweeps for. Each row below is one class: a regex the sweep applies to the lines a branch adds under the paths the row covers, outside the sites it exempts. The reviewer then verifies every hit in context against the owning layer's conventions document.

**What belongs here**

- Which escape classes this project has: the ways a change can bypass a symbol its conventions mandate, or a value a shared owner already holds, that a regex over added lines can catch.
- For each class: the regex that catches it, the layer paths it covers, the owner sites it exempts — the files that legitimately hold what the class forbids everywhere else — and what a hit is a candidate for.
- Worked examples for a front-end adopter follow. They are examples, not defaults: this project's classes come from its own conventions documents, and a class whose owner those documents do not name has no row here.
  - **Styling literal** — a color, size or spacing value written literally instead of taken from the mandated styling accessor.
  - **Timing literal** — a numeric duration or delay inlined instead of taken from the shared timing-constant owner.
  - **Duplicated shared constant** — a unit-local constant re-declaring a page size, limit or length cap that a shared owner already holds.
  - **Raw console / print call** — a diagnostic or error written straight to the language's console instead of through the mandated logger.
  - **Cast instead of mapping** — a wire-surface value cast to a richer type instead of going through the mandated mapping function.
  - **Invocation from the wrong layer** — a navigation, notification or dialog call made from a unit whose layer contract forbids it and requires a caller-supplied callback instead.
  - **Open literal set** — an ad-hoc union of literal values where the conventions document requires a declared closed type.

**How the rows are written and read**

- The rows sit in the one table directly under the exact heading `## Sweep rows`.
- The table's header row is exactly `| Escape class | Regex | Covers | Exempts | A hit is a candidate for |`, followed by its separator row and then one row per escape class.
- The table ends at the first line that does not begin with `|`.
- `Regex` is exactly one backtick code span holding a POSIX extended regular expression, the dialect `grep -E` reads. A literal `|` inside it is written `\|`, and a regex cannot contain a backtick.
- `Covers` is one or more code-spanned repo-relative paths separated by `, `. Each is a `layers[].path` value or a path beneath one, and `.` is the whole repository.
- `Exempts` is code-spanned repo-relative paths or git pathspec globs separated by `, `, or the single character `—` for none.
- The last cell is prose.

A hit is a lead to verify in context, never a finding by itself. The rows are maintained by you, by hand or with the command in the block that follows.

```
/devscene:analyze sweep
```

A lesson in the lessons ledger is not a row. The rows are read as the default branch commits them, so an edit made on a branch takes effect once it is merged.

## Sweep rows

| Escape class | Regex | Covers | Exempts | A hit is a candidate for |
|---|---|---|---|---|

_Run the command in the block below to fill this in from this repository's own code, or replace everything above by hand, keeping the `## Sweep rows` heading and its header row; either way this file is yours from here on and a re-run of the setup command keeps your copy — and if you write it by hand, the marker on the last line goes with it._

```
/devscene:analyze sweep
```

<!-- devscene:unfilled -->
