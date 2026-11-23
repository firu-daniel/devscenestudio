# Review — 03-native-vs-cross-effort.md
> Reviewer verdict: PASS WITH FIXES · Date: 2026-11-12

## Summary

The file's conclusion holds up: go cross-platform with a TypeScript UI, and don't build three native apps. The decisive harness facts check out in `/Users/daniel/Work/devscene`: remote runs are Linux-only, there is one preset per repo, there is no GTK preset, and `web-playwright` is the only working QA driver. Most career figures re-verify live: SO 2026, TIOBE Nov 2026, Oxylabs, Octoverse, Tauri/Wails/WinAppSDK release dates, Playwright and the Tauri WebDriver docs. The fixes fall into four groups:
- **Conflicts with 05.** Electron "direct reuse of the CLI". The Tauri/Rust career trade-off. "Users with no local setup need the npm CLI".
- **One overstated [verified] ranking.** JetBrains Promise Index "Go #3".
- **Cost-model hygiene.** The TL;DR and the table disagree, two rows are unexplained, and the matrix ratios are not derived from the model.
- **The "agents write faster" argument is one-sided in one place.** The harness's own review and parity agents are ignored.

## Must fix

**M1 — Electron "direct reuse of the `devscene` CLI's TS code" conflicts with 05.**
Location: TL;DR "Recommendation" bullet ("Choose **Electron** if agent-friendliness and direct reuse of the `devscene` CLI's TS code matter most"). §6 Electron row ("Same stack as the harness CLI and web app"). §4 CLI-as-core row ("the logic cannot drift from the plugin").
Problem: 05's TL;DR found that the run read/act logic is about 22.5k lines of per-repo **bash** (`harness-run-lib.sh`, `remote-run.sh`, `autonomous-watcher.sh`). It also found that the CLI has no `main`/`exports`, that on Windows the CLI must run **inside WSL** (so an in-process import in a Windows Electron main process probes the wrong OS), and that the scripts are versioned per repo with no `registry.json` schema field. So there is nothing for Electron to "reuse directly", and the logic *can* drift between repos. The file's own TL;DR bullet 5 and §4 already route everything through `devscene runs … --json`, so these sentences contradict the file itself as well as 05. I found no harness "web app" in the repo either.
Evidence: `05-harness-integration.md` TL;DR bullets 1–4 and 6.
Fix:
- Recommendation bullet: replace with "Choose **Electron** if agent-friendliness and having one language across the harness CLI, the app and the JSON contract types matter most. (Per 05, the run logic is per-repo bash, so there is no direct code reuse.)"
- §6: change "Same stack as the harness CLI and web app" to "Same language as the harness CLI".
- §4: change "the logic cannot drift from the plugin" to "the logic stays in the harness. Versions can still differ per repo until `registry.json` gets a schema field (see 05)".

**M2 — The Tauri "Rust only if the read-model lives in Rust" point is framed against 05's architecture.**
Location: §5 Tauri row ("Low Rust exposure if those are delegated to a Node sidecar or the CLI. The two career goals conflict with Issue item 7"). §4 CLI-as-core ("Users with no local harness setup still need the npm CLI installed"). Risks bullet 4 ("If the read-model must work with only `gh` and `git`, the core moves into the app").
Problem: The basic point is right. Tauri gives real Rust exposure only if non-trivial logic lives in `src-tauri`, since about 80–90% of the code is the TS frontend. The conflict with item 7 is overstated, though, and the sidecar option is out of date.
1. 05 recommends **no Node sidecar** ("Tauri no longer needs a Node sidecar").
2. 05 recommends an **app-side read-only GitHub read-model through `gh`** (shape d) for users with no local setup. Issue #1 also names `git`/`gh` as the primary data source ("some users … have no local plugin, watcher or logs"). So "users with no local setup still need the npm CLI" is wrong. That read-model must live in the app in every option.
3. The app-side work exists whatever the harness does: the `gh` read-model, the process transport (direct spawn or `wsl.exe`), log tailing and folder watching (05 notes that 9P gives no change notifications). In Tauri that work sits naturally in Rust commands, and **none of it duplicates item 7**. What would duplicate item 7 is re-implementing the *local run* logic (registry parsing, branch derivation, pause/resume) in Rust instead of calling `devscene runs --json`.
Evidence: `05-harness-integration.md` TL;DR bullets 5 and 6. Issue #1 "Data source" bullet (`gh issue view 1 --repo firu-daniel/devscenestudio`).
Fix: rewrite the §5 Tauri cell as:
"**High (TS) + moderate (Rust)** if the app-side layer lives in Rust commands: the `gh` read-model, the `devscene`/`wsl.exe` process transport, log tail and file watching. That does not conflict with Issue item 7, which only rules out re-implementing local run logic outside the harness. Rust exposure is low if those are done from JS through `tauri-plugin-shell`/`plugin-fs`."
Then:
- Delete "still need the npm CLI installed" from §4.
- Change Risks bullet 4 to "Per 05, the GitHub-side read-model lives in the app in any case. The open choice is only its language (TS vs Rust)."
- Reword Risks bullet 5 to match.

**M3 — JetBrains Promise Index "#2 Rust / #3 Go" is overstated as [verified].**
Location: TL;DR career bullet. §5 table column "JetBrains Promise Index 2025" (Rust **#2**, Go **#3**). Q3 answer ("Promise #2").
Problem: The primary post does not number the ranks. It says "TypeScript, Rust, and Go boast the highest perceived growth potential". A secondary report gives a different order: "TypeScript (No. 1), Rust (No. 2), Python (No. 3), Go (No. 4), C++ (No. 5)". Go #3 is therefore contested, and the source is 13 months old.
Evidence: https://blog.jetbrains.com/research/2025/10/state-of-developer-ecosystem-2025/ (fetched via curl; WebFetch gets 403). https://awsinsider.net/articles/2025/10/20/aws-swamps-gcp-azure-among-developers-in-ecosystem-report.aspx
Fix: replace the ranks with "top group (TS, Rust, Go per JetBrains; one secondary report ranks Python #3 and Go #4)". Tag the numeric ranks [secondary]. In Q3, change "Promise #2" to "in JetBrains' top-growth group".

**M4 — Cost-model headline figures are inconsistent, and some ratios have no derivation.**
Location: TL;DR bullet 1 vs the §1 table vs §6 / Q2.
Problems:
1. The TL;DR says **2.0–2.3×** v1 and **2.5–2.8×** per feature. The table gives **2.1–2.2×** (57–59 / 27, arithmetic checked) and **2.6–2.8**. The text and §6 say **≈ 2.7×**. Pick one set. If 2.0–2.3 is meant as the ±30% sensitivity band, say so: native UI row +30% gives ≈ 2.28–2.37×, and cross UI row +30% gives ≈ 2.0×.
2. The "Native ×3 + shared core" column is *higher* than plain native ×3 for packaging (8 vs 7.5) and CI (4.5 vs 4), and no reason is given. The CLI is installed by the user, so nothing extra is bundled. Either explain why (for example, the CLI-version handshake and the `wsl.exe` transport tested in CI) or set them ≤ native. Recomputed with 7.5 and 4, the total is 44 (≈ 1.63×), so the headline barely moves.
3. In the §6 matrix, the ratios for Tauri (≈ 1.05×), Wails (≈ 1.05×), Compose/Flutter/Avalonia (≈ 1.2×) and their per-feature figures do not come from §1, which models only "Electron/Tauri" as one column. The 1.4× for WSLg also conflicts with §4's 1.3–1.5×.
Fix: align the TL;DR to the table. Add one line under the table stating the row-level assumptions: agents write about 90% of the code, owner review time scales with diff size × language unfamiliarity, and agent wall-clock time is free. Annotate the matrix: "ratios outside §1 are judgement calls **[inferred]**, not model outputs". Add a 3-row sensitivity table (UI ±30%, review ±30%, packaging ±30%) to back the "robust to ±30%" claim in Risks.

## Should fix

**S1 — "Agents write faster" is handled fairly toward cross-platform but not toward native.**
Location: §1 "How to read it" bullet 2 ("Agents … do not compress … reviewing diffs in three languages"). TL;DR bullet 1 ("agents do not speed those up").
Problem: This is too absolute. The harness ships review agents (`branch-reviewer`, `skeptic-reviewer`, `layer-reviewer`). It also ships a **parity phase**, `business-parity-reviewer`, whose stated job is keeping code in parity with a reference implementation. Porting an already-reviewed SwiftUI feature to GTK/WinUI is close to the best case for agents: translation with a spec and a reference. That lowers the "UI" and "parity checks" rows for native. The counterweight is real and is in §2: those reviewers are read-only and cannot run WinUI/Swift gates on Linux. So the net effect is smaller than "×N" but not zero.
Evidence: `/Users/daniel/Work/devscene/plugin/agents/` (business-parity-reviewer, branch-reviewer, skeptic-reviewer). `harness.config.json` `phases.parity`.
Fix: add a bullet. "Counter-argument: the harness's review and parity agents can pre-review ports against a reference implementation, which could cut native UI cost toward ≈ 12 O-d (ratio ≈ 1.9×). They cannot compile or run gates for WinUI, or for SwiftUI in remote runs, so owner review is still the backstop." Soften "do not speed those up" to "speed those up much less than writing".

**S2 — "Web QA works" for Electron/Tauri/Wails needs a qualifier.**
Location: TL;DR bullet 3 ("A webview UI … is the only kind the harness's QA agent can drive today"). §3 Electron/Tauri rows. §6 "`web-playwright` QA works".
Problem: The `web-playwright` qa-tester navigates a Playwright browser to `base_url`, served by `commands.devServer`. It never launches the desktop shell. Outside the shell the renderer has no IPC: Tauri `invoke`, Electron preload APIs and Wails bindings are all missing. So harness QA works only if the app ships a **browser mode with a mocked or HTTP-backed backend**. That is a real design requirement, and it applies equally to all three webview options. Playwright `_electron` is not the harness driver.
Evidence: `/Users/daniel/Work/devscene/plugin/agents/qa-tester.md` (lines 31–39, 63–70: `base_url`, `commands.devServer`, "You never start … the application's server"). `cli/src/config/model.ts` `QA_DRIVER_IMPLEMENTED`.
Fix: append "…provided the UI has a browser mode whose IPC layer is mocked or served over HTTP. Add this as a v1 architecture requirement."

**S3 — Harness §2: claims are correct, but some consequences are imprecise.**
All four load-bearing claims verified:
- `remote-execution.md` §8 says "**Not supported:** macOS and Windows GitHub-hosted runners", and every workflow template uses `runs-on: ${{ vars.DEVSCENE_RUNNER || 'ubuntu-latest' }}`. A self-hosted runner "is any Linux machine you own".
- `DETECTION_PRESET_NAMES` matches the file's list and has no GTK/meson/Vala entry. A grep of `cli/src` for gtk|meson|winui|xaml|tauri|electron finds nothing.
- `nestedApplication.ts` returns silence when two or more child apps are found.
- `QA_DRIVER_IMPLEMENTED` has only `'web-playwright': true`.

Precision fixes:
1. `nestedApplication.ts` is **advisory only**. Its header says "nothing is derived from what it finds. No preset, no layer …", and it only prints an `--app-dir` hint. "Gives up on multi-app" is true, but even a single hit would not create a layer profile. The real path is the `monorepo` preset plus manually split layers and wrapper scripts. The harness's own repo is configured exactly that way (`/Users/daniel/Work/devscene/harness.config.json`: preset `monorepo`, layers `cli`/`plugin`/`general`, `commands.typecheck: bash scripts/typecheck.sh`). So the obstacle is **which OS the gates run on**, not the preset machinery.
2. `COMMAND_FAMILIES` is not pure "first hit wins". `SIGNAL_COMMAND_FAMILY` hoists the family of the matched preset signal to the front (`presets.ts` ~1980–1999).
3. "Remote is the repo default (Issue #1)" is the *app's* intended setting. In the harness, `local` is still the default and remote is opt-in (`ROADMAP.md` line 125). A local run on a Mac (Seatbelt sandbox, ROADMAP line 153) can build SwiftUI, which the file does say elsewhere.
4. "Gates blind to two of three codebases" refers to the harness's agent loop. Ordinary CI on `macos-latest`/`windows-latest` would still catch build breaks after a push, just outside the agent's fix loop. Say so.

**S4 — Close the open ROADMAP question.**
Location: Risks bullet 3 ("Check the harness ROADMAP before final sign-off").
Evidence: I checked `/Users/daniel/Work/devscene/ROADMAP.md`. It has no row for macOS/Windows runners and none for a desktop QA driver. The only QA-driver row is "Mobile QA drivers … Open" (line 130).
Fix: "Checked 2026-11-12: ROADMAP plans no macOS/Windows runner and no desktop QA driver. Only mobile drivers are open."

**S5 — The agent-effectiveness evidence is older and weaker than its tags.**
1. **SwiftEval.** "3 of 35 benchmarks include Swift" is stated on the page. "41 of 44 models score lower" is **derived by counting the Δ column** (only GPT-3.5 Turbo and CodeLlama 13B/34B score higher on Swift). The model set is 2024-era (GPT-3.5, CodeLlama), and the paper is from Jan 2025 (FORGE'25), so it is >12 months old. Flag it as old, as the file already does for the SWE-bench rows.
2. **Xcode 26.3.** Preview capture over MCP (`xcrun mcpbridge`) and "AI coding only on macOS 26" are confirmed, but only through **InfoQ (secondary)**, while TL;DR bullet 4 tags it **[verified]**. Cite Apple's Xcode 26.3 release notes or newsroom post, or Anthropic's announcement, or else tag it [secondary].

Evidence: https://research.macpaw.com/projects/swifteval · https://infoq.com/news/2026/02/xcode-26-3-agentic-coding

**S6 — The pay comparison is global and the gap is small.**
Location: TL;DR career bullet. §5 "Role pay".
Problem: The figures are right ($85,296 back-end, $84,277 mobile, $80,000 desktop/enterprise with n = 559, $79,610 full-stack, $70,320 front-end), but they are **global** medians in USD. The gap is about 6%, and desktop pays more than full-stack. That is weak support for "career value lies in the language, not desktop-GUI skill".
Evidence: https://survey.stackoverflow.co/2026/work/data
Fix: add "(global medians, USD)". Soften to "role pay differs little (desktop ≈ 6% below back-end, above full-stack). Career value comes mainly from the language."

**S7 — Octoverse details.**
TS #1 is confirmed: 2,636,006 monthly contributors, +66.6%, August 2025. C# +22.22% YoY contributors is confirmed. Two qualifiers are missing:
- The "94% of LLM compilation errors were type-check failures" figure is GitHub **citing a 2025 arXiv paper**, so it is secondary.
- The post dates from 2025-10-28 (updated 2026-02-28), so it is more than 12 months old.

Evidence: https://github.blog/news-insights/octoverse/octoverse-a-new-developer-joins-github-every-second-as-ai-leads-typescript-to-1/
Fix: tag the 94% figure [secondary] and add the age flag.

## Nice to have

**N1** §3 Multi-SWE-bench row: the Python cell "36.2% (SWE-bench)" comes from a different benchmark. Move it to a footnote so readers don't compare it across the row.

**N2** SWE-bench Multilingual is cited from kabirk.com. Prefer the primary leaderboard at https://www.swebench.com/multilingual.html.

**N3** "GTK and WinUI have no equivalent" (agent UI visibility): this is true for first-party preview capture. But Windows UI Automation–based MCP servers and generic computer-use agents exist. Soften to "no first-party preview/inspection tooling for agents".

**N4** Say explicitly that the cost of building `devscene runs … --json` (05 estimates 1.2–2k lines) is excluded from every column, because it is harness-side and common to all options.

**N5** Verified as stated, no change needed:
- SO 2026: TS 43.8/53.0/27.5, Rust 18.0/67.4/26.3, n = 14,099, and all other rows in §5.
- TIOBE Nov 2026: Go #10, Rust #11 ("dropped out of the Top 10, losing its position to Go"), Swift 18, Dart 20, Kotlin 33, TS 41.
- Oxylabs: Go 5%, TS 8%, JS 19%, Python 46%, about 800k postings, Jan 2025–Mar 2026.
- Tauri: v3.0.0-alpha.6 on 2026-11-06 and v2.12.5 on 2026-10-21.
- Wails: v3.0.0 on 2026-10-26, v3.1.0 and v2.17.1 on 2026-11-01.
- WinAppSDK: 2.0.1 on 2026-04-29 and 2.6.5 on 2026-11-02.
- Playwright Electron: "experimental", v21+.
- tauri-driver: Windows/Linux only. macOS is covered by the WebdriverIO embedded server, or by the CrabNebula fork with a paid key.

## Review resolution

Resolved 2026-11-12 by the fix agent. Harness claims re-checked in `/Users/daniel/Work/devscene`: `remote-execution.md` "Not supported: macOS and Windows GitHub-hosted runners", `QA_DRIVER_IMPLEMENTED`, the `nestedApplication.ts` header, `SIGNAL_COMMAND_FAMILY`, `harness.config.json` (preset `monorepo`, `phases.parity`), `plugin/agents/business-parity-reviewer.md`, the qa-tester `base_url`/`commands.devServer` lines, and ROADMAP lines 125 and 130. The SWE-bench Multilingual primary page was fetched live. The JetBrains post could not be re-fetched (blocked), so M3 relies on the review's evidence. M3 only lowers confidence, so it is safe to apply.

- **M1 — applied.** TL;DR recommendation, §6 Electron row ("Same language as the harness CLI") and §4 CLI-as-core row reworded as the review proposed. The TL;DR hybrid bullet, the §4 Rust row and the §5 Electron row also no longer imply TS code reuse.
- **M2 — applied.** The §5 Tauri cell is rewritten: Rust exposure comes from the app-side layer (`gh` read-model, `devscene`/`wsl.exe` transport, log tailing, file watching); only local run logic belongs to the harness CLI; no Node sidecar. "Still need the npm CLI installed" is deleted. Risks bullets 4 and 5 are rewritten. Q3 and the TL;DR recommendation are aligned. The §6 tie-break was re-checked and still holds: Electron's side narrows to agent-friendliness and one language, and Tauri's career case gets cleaner. 04's tie-break criterion now reads "WSL access from Rust vs Node" instead of "from WebView2".
- **M3 — applied.** Numeric Promise Index ranks were replaced with "top-growth group". The ranks are tagged [secondary] with source 26c. Q3 and the TL;DR are updated. Python's cell no longer says "top tier".
- **M4 — applied.**
  - The figures now agree everywhere: v1 native ×3 is 57–59 / 27 = 2.1–2.2×, per feature 2.6–2.8× (≈ 2.7×). This holds in the TL;DR, the table, the prose, Q2 and §6.
  - The shared-core packaging/CI anomaly is corrected to 7.5 / 4, equal to native ×3, because nothing extra is bundled and the handshake test sits in the tests row. The total is 44 (1.63×, ≈ 1.6×). §4 and §6 are updated from 1.65×.
  - Row-level assumptions and the exclusion of the harness JSON verb from every column (N4) are now stated under the table.
  - The per-feature ratios are now derived from §1 row ratios with a stated feature mix, tagged [inferred]. This changed shared-core per feature from 2.2 to ≈ 1.9 and 2-codebase from 1.8 to ≈ 1.7.
  - Added a 3-row sensitivity table (UI, review, packaging ±30%; symmetric and one-sided). The Risks text is corrected to match: 1.9–2.4×, and 1.7–2.6× for a one-sided review error. "Robust to ±30%" was only true for symmetric errors.
  - §6 marks model outputs with † and states that all other ratios are [inferred] judgement calls, with the basis shown for Tauri/Wails 1.05×, Compose/Flutter/Avalonia 1.2× and WSLg. WSLg is aligned to §4's 1.3–1.5×, with its derivation.
- **S1 — applied.** Counter-argument bullet added in §1 with the harness review and parity agents and the ≈ 12 O-d UI. The ratio is given as ≈ 1.9–2.0× rather than ≈ 1.9×: UI 12 alone gives 54/27 = 2.0×, and the parity checks must also go to zero to reach 1.93×. Added the caveat that `business-parity-reviewer` checks business logic, not UI behaviour. "Do not speed those up" is softened in the TL;DR and §1.
- **S2 — applied.** Browser-mode qualifier (mocked or HTTP IPC) added to TL;DR bullet 3, §2 QA row, §3 Electron/Tauri/Wails rows and §6. It is listed as a v1 architecture requirement in TL;DR and Risks.
- **S3 — applied.** All four precision fixes are in §2: `nestedApplication.ts` is advisory only and the harness repo uses the monorepo + manual layers path; the `SIGNAL_COMMAND_FAMILY` hoist; remote is the app's intended default while harness `local` stays the default, and a local Mac run can build SwiftUI; ordinary per-OS CI still catches breaks outside the agent loop (also in TL;DR bullet 2).
- **S4 — applied.** The Risks bullet now records the ROADMAP check: no macOS/Windows runner and no desktop QA driver; only mobile drivers are open.
- **S5 — applied.** SwiftEval is flagged as >12 months old with 2024-era models, and 41/44 is marked as derived from the Δ column (§3, TL;DR, source 9). Xcode 26.3 is tagged [secondary] in the TL;DR and §3. No Apple primary source was added.
- **S6 — applied.** "Global medians, USD" and n = 559 added. The claim is softened to "role pay differs little (desktop ≈ 6% below back-end, above full-stack); career value comes mainly from the language" in §5 and the TL;DR.
- **S7 — applied.** The 94% figure is tagged [secondary] (GitHub citing a 2025 arXiv paper). The Octoverse age flag is added in §3, the TL;DR and source 10.
- **N1 — applied.** The Multi-SWE-bench Python cell is now "n/a¹", with a footnote.
- **N2 — applied.** The primary page swebench.com/multilingual.html was fetched and added as [6]. It confirms 300 tasks, 9 languages, 42 repos, Rust highest and C/C++ lowest. The per-language percentages appear only in a figure there, so kabirk.com is kept as [6b] for the numbers. While checking, I also corrected "about 43 per language" to "about 33 per language" (300/9; 43% is the overall resolution rate).
- **N3 — applied.** Changed to "no first-party preview/inspection tooling for agents", with UI Automation / computer-use agents noted (TL;DR, §3 GTK and WinUI rows).
- **N4 — applied.** The exclusion is stated in the §1 row-level assumptions.
- **N5 — no change needed.** These items are verification notes.
