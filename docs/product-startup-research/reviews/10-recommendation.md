# Review — 10-recommendation.md (and README.md)
> Reviewer verdict: PASS WITH FIXES · Date: 2026-11-12

## Summary

10 is a faithful synthesis on most checked points. Every spot-checked number from 03 (27 / 28.4 / 57–59 O-d, 2.1–2.2×, ≈ 2.7×, +1.4 O-d Rust premium), 06 (48–82 O-d, the ≈ 15× per-PR CI gap, the Run-gates park), 08 (5.5 / 6.0 / 5.75 O-d with ranges, 29 controls, H1–H12 severities), 09 (the "Not in doubt" items, the three narrow questions, email items a–f), 07 (scores 103/99/92/84, the four delivery modes, the local-runs gate) and 01 (the shortlist order Electron > Tauri 2 > Wails 3) matches the reviewed area files. The harness follow-up list covers every 08-H and 09-H item and the 06-H set, with no duplicates.

**The label-prefix claim is correct.** `cli/src/remote/githubActions.ts:136` is `export const STATE_LABEL_PREFIX = 'devscene: ';`. `STATE_LABELS` builds `devscene: running|parked|paused|done|failed|stopped` from it, and `remote-run.sh:290` sets `devscene: running` on the issue. Issue #1 item 5 says `sdlc-harness: <state>`, so it is wrong, and so are 08 §1.3 (line 102) and §3.12 (line 420). `sdlc-harness/` survives in the harness only as an old `stateDir` in tests.

Three problems need fixing:
- The Tauri-default argument says Tauri's security advantage "cannot be bought back". 08 prices it as buyable. The decision therefore rests mainly on the owner's preference for Rust exposure, and 10 does not say so.
- The closed-source cost figures use an open-source-only certificate.
- The v1 scope (local start, pause, global stop) depends on contract verbs that D6 and follow-up #2 schedule for v1.1/v1.2 or leave out.

10's harness follow-up list never cross-references 11 or devscene #170.

## Must fix

**M1. §1.2 "Reading", §2 row 1, TL;DR bullet 1, README "Why Tauri": the Tauri default leans on career preference more than it admits, and the security half of the argument is overstated.**
- **Problem 1: security can be bought back, and 10 says it cannot.** 10 says "Tauri's two wins cannot be bought back in Electron … the Chromium patch treadmill is structural". 08 says otherwise:
  - 08 §6.1 grades Electron "Recommended (**equal if the release cadence is kept**)".
  - 08 §4.2 prices that cadence at ≈ 0.25 O-d per bump, ≈ 1.6 O-d/yr.
  - The sha512-only Linux updater is closed by a signature hook (08 §3.6).

  So Electron can buy back the security gap for roughly 1.6 O-d/yr plus a small one-off hook. Over two to three years that is about the same as Tauri's extra cost: +1.4 O-d effort, +0.5 O-d security and a v3 migration.
- **Problem 2: the security row leaves out Tauri's Linux downside.** The row lists only "OS-patched WebView2/WKWebView". 07's TL;DR records 6 WebKitGTK advisories in 2026 and LTS distros lagging upstream. 08 Risk 7 says Trusted Types may be missing on LTS webkit2gtk-4.1 below 2.50. On Linux, Tauri's webview is patched only as fast as the distro patches it.
- **Problem 3: career value is not a clean Tauri win.** 03 §6 rates **both** Electron and Tauri ●●● for career value. 03 §5 calls Tauri's Rust exposure "moderate" (80–90% of the code is TS), and TS is "the strongest single bet". 10's row ("TS only" vs "**TS + Rust**") reads as a clear win. The real gain is moderate Rust exposure, which only appears if the owner puts the app-side layer in Rust.
- **Problem 4: §2 row 1 truncates 07's flip criterion.** 10 quotes "security weighted above everything moves Tauri above Electron". 07's full sentence continues: "**non-webview toolkits above both**". Cut short, the quote supports Tauri more than 07 does.
- **Problem 5: §1.2 has no developer-experience row.** 07 weights DX high (×3) and scores Electron 5 vs Tauri 3: cold Rust builds of 3–8 min, and platform dev packages on every contributor machine (07 §7). 07's 15-point gap is mostly agent QA, DX and observability. A one-step increase in 07's security weight moves Tauri by only 3 points.
- **Evidence:** 08 §4.2 and §6.1; 03 §5 and §6; 07 TL;DR bullet 5, §7 and "Criteria that could flip the framework order".
- **Fix:**
  - Rewrite the §1.2 "Reading" paragraph to: "Electron wins more rows, which is why 01 and 07 rank it first. On security, Tauri has a modest structural edge: a mandatory signed updater, a capabilities ACL, and no Chromium to ship on macOS/Windows. 08 rates Electron equal if its 8-week cadence (≈ 1.6 O-d/yr) and a Linux signature hook are kept, and on Linux Tauri depends on distro WebKitGTK patching. **The deciding factor is therefore the owner's wish for real Rust exposure.** Electron cannot provide it, and 03 counts it only as moderate exposure. If the owner does not value that, Electron is the better default."
  - Add a DX row to the §1.2 table (Electron: Node only, seconds; Tauri: Node + Rust + platform deps, cold build 3–8 min; source 07 §7).
  - Add the WebKitGTK LTS patch lag to the security row (07 TL;DR, 08 Risk 7).
  - Quote 07's flip criterion in full.
  - Mirror these changes in the TL;DR bullet and the README's "Why Tauri" bullet.
  - Make D1 a **now** decision: does the owner value moderate Rust exposure at ≈ 1.4 O-d plus the v3 migration and WebKitGTK risk? Flip condition 4 is a preference, and the spike cannot measure it. If the answer is no, the spike can be scoped down to Electron.

**M2. §7 money table, §2 row 6, D2, D3, TL;DR "Money", README "Cost": the closed-source signing cost uses an open-source-only product, and the open-source saving does not reconcile with §7.**
- **Problem 1: the lower bound is wrong.** The closed-source column gives Windows signing as "≈ 30–500 (OV)", and its lower bound comes from Certum's **Open Source** Code Signing card variants (€25/€69). §2 row 6 says the same ("€25–€69 Certum card variants"). That product is for open-source developers (01 §4b, source 38: `shop.certum.eu/open-source-code-signing-on-simplysign.html`). It does not apply to a closed app. For a closed app, the OV figure is Microsoft's US$300–500/yr (04 §7, source 43). 01's "€50–€300/yr" is the general OV range. The closed-source total therefore starts well above ≈ US$130.
- **Problem 2: D2 and §7 disagree.** D2 says open source "saves about US$420–810/yr (07 §6)". 10's own §7 table implies a saving of ≈ US$31–501, or ≈ 800 only with Sentry Team. 07 §6 reaches 420–810 by counting Sentry Team (US$312), and also says that saving "may not be a real saving".
- **Fix:**
  - Closed column, Windows signing: "≈ 120 (Artifact Signing, if eligible) or ≈ 300–500 (OV; Microsoft's range, 04 §7)".
  - Total recurring: "≈ 220–600 (up to ≈ 900 with Sentry Team)".
  - §2 row 6: "budget for an OV certificate (US$300–500/yr; Certum's €25–€69 Open Source variants only if the app is open source)".
  - D2: "saves about US$120–500/yr in signing, plus up to US$312 if Sentry Team would otherwise be needed (07 §6)".
  - Update the TL;DR money bullet and the README cost bullet to match.

**M3. §1.3, D5, D6, harness follow-up #2, §6 item 5: the v1 feature set depends on contract verbs that 10 schedules later or leaves out.**
- **Problem 1: the phasing does not fit the v1 scope.**
  - §1.3 puts local runs in v1 scope: "Issue item 12 (inbox drop) and item 15 (watcher status)".
  - D5's v1 is "board, detail, start, pause, global stop". §6 item 5 makes the one-click global stop a release gate.
  - D6 and follow-up #2 adopt 05 §5's phasing: v1 = `capabilities`, `runs list/show/watch`, `doctor --json`; v1.1 = pause/resume/answer; v1.2 = `drop`/`derive-branch`/`review`.

  So **local start (`drop`) arrives two harness phases after Studio v1 needs it, and pause one phase after**. 05's verb list has no global-stop verb at all. 05 does list `repos --json` (item 8) and `daemon status --json` (item 15), but 10's rank 2 drops them.
- **Problem 2: the line count is mislabelled.** D6 says "The read side is about 1–1.5k lines", yet its read-only phase includes `runs watch`. 05 sizes 1–1.5k **without** `watch` and says the "act side plus `runs watch` is several thousand lines … a component in its own right" (05 lines 14 and 217).
- **Fix:**
  - Choose one of two options: (a) move `pause`, `drop` and a global-stop verb (`runs stop-all` writing `AUTONOMOUS_STOP`, or the remote `stop` dispatch) into the harness phase Studio v1 depends on; or (b) cut v1 to remote-start-only (Issue trigger) plus read-only, and move local start and pause to v1.1.
  - State the choice in D5 or D6, and in §9 items 7, 11 and 12.
  - Add `repos --json` and `daemon status --json` to rank 2's v1 phase.
  - Change D6's size note to: "read side ≈ 1–1.5k lines excluding `runs watch`; `watch` and the act side are several thousand lines, to be sized in the harness repo (05 §5)".

## Should fix

**S1. §8 intro, ranks 1, 9 and 13, the "Deferred" row, and §9 "New item, Harness follow-ups": the list does not cross-reference 11 or devscene #170 (OPEN, "sandbox series: remaining steps").** §9 tells the owner to "open the §8 issues in `firu-daniel/devscene`" without checking existing issues first. 11 maps them against #170 item 10 and its linked issues. Add:
- in the §8 intro: "Before filing, see 11 (`11-harness-findings-vs-issue-170.md`), which maps each row to devscene #170 item 10 and its linked issues; file only the rows 11 marks not covered, and fold the rest into the issue 11 names."
- per row, a "Tracked in" column:
  - rank 1 (H1/H1′) → 11 says #170 does not fix it; the deny list could fold into #318's design questions, and #318 Q2 partly covers H1′;
  - rank 9 (09-H6) → candidate to fold into #309;
  - rank 13 (cargo cache) → partly #234;
  - Deferred 06-H3 → partly #241.
- in §9: change the item to "open the issues 11 lists as not covered by #170, and link them".

**S2. §8 ranking and D5: the severity labels are not all sourced, and one contingency is missing.**
- (a) The list is introduced as "Ranked by severity". Rank 2, the `runs --json` contract, is a feature dependency, not a vulnerability. It is labelled **High** and absorbs 08-H10, which 08 grades **Low**. Ranks 8 and 9 (09-H5, 09-H6) get "Medium", but 09 assigns no severity to its harness items. **Fix:** retitle the list "ranked by priority for Studio (severity from 08 where it has one)". Tag the 09 rows and rank 2 "[10's grading]".
- (b) 08 Risk 1 says that if every write in the runtime measurement is refused, "H1/H1′ drop to Info". D5 says "Ship v1 without answer/resume unless H1/H1′ are fixed first". **Fix:** "… unless H1/H1′ are fixed, or the 08 Risk 1 measurement shows every write refused (they then drop to Info)". Add the same clause to rank 1.

**S3. §3: the owner's question 1 ("Are there cross-platform solutions … which are credible in late 2026?") has no explicit answer.** §3 begins at "worth it versus native". The answer appears only implicitly in §1.1. **Fix:** add §3.0, based on 01 Q1: "Yes. Credible: Electron, Tauri 2, Flutter, Compose Multiplatform, Avalonia, Qt/PySide6, plus Wails 3 (stable since 2026-10-26). Riskier: Electrobun, Flet/Toga, Rust-native toolkits. Out: MAUI and React Native desktop (no Linux), Xamarin (EOL). → 01 TL;DR, Q1, ranked shortlist."

**S4. §3.1 and §2 row 8 leave out the intermediate native options that 03 and 06 evaluated.**
- 03 offers a shared-core variant (native ×3 + CLI core, ≈ 1.6×, 44 O-d) and a two-codebase split (SwiftUI on Mac + one cross build, ≈ 1.5×). 03 calls the latter "the only native variant worth considering … only if a native Mac feel is a product requirement" (03 TL;DR, §4).
- 06 costs A′/A″ at ≈ 38–63 / 33–53 O-d of harness work (06 §2.4, §2.6).
- 10 presents only "native ×3 vs cross".

**Fix:** add one sentence to §3.1: "Intermediate options cost less (≈ 1.5× for SwiftUI-on-Mac + Tauri/Electron elsewhere, ≈ 1.6× for native ×3 on the CLI core) but still need 33–63 O-d of harness work and leave Swift unverifiable in remote runs (03 §4, 06 §2.6). Consider them only if a native Mac feel becomes a product requirement."

**S5. §5 spike: some days are overloaded, and hardware and accounting gaps are unstated.**
- Day 1 (web UI, browser mode, Playwright QA, XSS corpus) and Day 2 (Rust core, transport, native modal, isolation, locked capabilities, the Electron comparison shell, and five measurements) are each a day of owner review only if almost nothing goes wrong. 03's model puts the whole data and process work at 7 O-d.
- The argv fuzz with a mocked `wsl.exe` on a Windows runner is listed under "What to build" but is in no day.
- Days 3 and 4 need hardware the owner may not have. The research mentions only an M4 Mac. The plan needs a Linux box with an NVIDIA GPU on Wayland (VMs cannot reproduce DMABUF/NVIDIA bugs), a Windows 11 machine with WSL2, and optionally Windows 10.
- "≈ 6.5 owner-days" counts the optional +0.5 Electron CDP day but not the Day 0 admin.
- §7 adds the full spike to the full v1 although "about 60% of it carries into v1" (that 60% is also untagged; tag it [inferred]).

**Fix:**
- Size the spike at 6–8 O-d, or split Days 1 and 2 into 1.5 days each.
- Schedule the argv fuzz (Day 4).
- Add a "hardware needed" line, and say which tests drop if that hardware is unavailable.
- State that ≈ 3.9 O-d of the spike is credited against v1 in §7, or drop the 60% claim.

**S6. Placement of the flip conditions.** The TL;DR and §4 D1 send readers to §3.4 for the flip conditions, but they sit at the end of "Native-side blockers with a cross-platform framework". **Fix:** move them to §1.2 (after "Reading") or to a §1.6 "When to switch to Electron", and update the TL;DR and D1 references. Condition 4 should point to D1 as a now-decision (see M1).

**S7. README.md.**
- (a) The Files table has no row for `11-harness-findings-vs-issue-170.md`. Add one: "Maps 08/09/05/06 harness findings to devscene #170 item 10 and its linked issues; lists the issues still to file", with verdict "Not reviewed".
- (b) The 10 row says "Not reviewed (synthesis)". Change it to "PASS WITH FIXES · [review](reviews/10-recommendation.md)".
- (c) The "Flip to Electron" bullet leaves out the owner-preference condition (10 §3.4 item 4). Add "or if you don't value Rust exposure enough to pay for it".
- (d) Apply M2's cost fix to the "Cost" bullet.
- All existing links and file names resolve. The 01–09 verdicts match `reviews/*` (all PASS WITH FIXES, each with a "Review resolution" section), and every area file is `Status: reviewed`.

**S8. §3.3 and §3.10 contradict each other on Kotlin.** §3.3 says "Kotlin's career value outside Android is moderate (03 §5)". §3.10 says "Kotlin outside Android … carr[ies] little transferable value". 03 itself says "Moderate" in §5 and "little" in its TL;DR. **Fix:** use 03 §5's wording in both places: "moderate (Android and JVM back-end); desktop Compose is niche".

## Nice to have

**N1. §2 row 1.** Delete "Note: 07 does not lean Tauri, contrary to how it is sometimes summarised; only 08 and 03's career column do." It is a process remark, and 03's career column rates both ●●● (M1).

**N2. §9 item 5.** Besides the label prefix, the run titles in Issue item 5 are incomplete. `devscene-run.yml:425` is `run-name: harness ${{ inputs.action }} ${{ inputs.branch }}`, with `action ∈ {run, pause, warm, stop}` (`:430-438`). Suggested text: "Actions runs titled `harness <action> <branch>` (`run`, `pause`, `warm`, `stop`)".

**N3. §6 item 2 ("the isolation pattern on") and "Every item is a release gate".** 08 §4.1 row 13 marks the isolation pattern **S**, but 08 §6.2 item 8 lists it in the minimum bar. Cite 08 §6.2 item 8 so the stricter reading is visibly deliberate.

**N4. TL;DR and §3.8 "three CI suites".** 08's TL;DR names the third suite as DNS-rebinding/CSRF/WebSocket (local modes). For the desktop shell, 10 substitutes the hostile-repo fixture. That is correct for the shell, but say so: "for the desktop shell: XSS corpus, argv fuzz, hostile-repo fixture (08 §4.3 #1, #2, #5)".

**N5. §1.2 "Bundle size" row.** Tauri's "≈ 3–60 MB" is the macOS/Windows figure. A Linux AppImage that bundles WebKitGTK grows to 70 MB+ (04 §5). Add "(Linux AppImage 70 MB+)".

**N6. §3.2 RAM ratios.** "Within about 2× on RAM" and "Electron … 2–4× the RAM" are tidier than 02's data: Tauri 88–109 MB vs native 30–70 MB, Electron 128–600 MB, and 02 notes sources "disagree by 2–4×". Use 02's own ranges instead of the ratios.

**N7. §3.9.** Carry 09's grades. "Spawning the unmodified binary matches the legal page's carve-out" is **[strong reading]** in 09, not [unambiguous]. Add 09's other [ask], sustained unattended use on a personal plan (email item b), which §3.9 omits.

**N8. §4.** The UI library ("React or Svelte", §1.5) is not posed as a decision. Add it as D11, or say explicitly that it is deferred to the spike's Day 1.

**N9. §9.** Item 6 (log history) gets no update, although 08-H3 is directly relevant: the `harness-state` artifact keeps logs for 400 days, and on public repos they are readable by any signed-in user. Suggested addition: "Item 6: treat run logs on public repos as public (08 H3); prefer the committed analytics summary".

## Checks performed

- `gh issue view 1 --repo firu-daniel/devscenestudio`: item 5 reads "`sdlc-harness: <state>` labels" and "Actions runs titled `harness run <branch>`".
- `/Users/daniel/Work/devscene` at `a1d0e992`:
  - `cli/src/remote/githubActions.ts:136` (`STATE_LABEL_PREFIX = 'devscene: '`) and `:141-152` (`RUN_STATES`, `STATE_LABELS`);
  - `cli/templates/scripts/remote-run.sh:290`;
  - `cli/templates/github/workflows/devscene-run.yml:20, 425, 430-438`.
- Area files read against 10:
  - 01 TL;DR, §3, §4, Q1/Q6/Q7, the ranked shortlist;
  - 02 TL;DR, §3, §4, §6, §8, §9;
  - 03 TL;DR, §1–§6, Q2/Q3, Risks;
  - 04 TL;DR, §4–§8 excerpts;
  - 05 TL;DR, §3, §5;
  - 06 TL;DR, §1.2, §1.7, §2.1–§2.6, §3;
  - 07 TL;DR, §4–§7, Risks, Scoring;
  - 08 TL;DR, §4.1–§4.4, §5.2–§5.3, §6.1–§6.2, Risks;
  - 09 header block, TL;DR, F7, F8, checklist, harness items, email, Risks.
- 11 was read only for its scope and TL;DR, to place the cross-references in S1. It was not reviewed.

## Review resolution

Fix agent, 2026-11-12. Each finding was re-checked against the area files before it was applied. `10-recommendation.md` is now `Status: reviewed`.

**Owner clarification applied during the fix.** The owner's interest in Rust, and in career languages generally, is a mild wish that every other criterion outweighs. D1 was therefore re-decided on the evidence criteria alone, with security first. **The default is now Electron, with Tauri 2 as the alternative**, and the spike validates the pick. This goes further than M1's suggested fix, which kept Tauri as the default and called Rust exposure the deciding factor.

| ID | Outcome | Notes |
|---|---|---|
| M1 | **Applied, with a different conclusion** | All five problems were confirmed. The security row now carries 08 §6.1's "equal if the release cadence is kept" (≈ 1.6 O-d/yr, 08 §4.2), the Linux signature hook (08 §3.6) and Tauri's WebKitGTK patch lag on Linux (07 TL;DR, 08 Risk 7). The career row shows 03 §6's ●●● for both and calls the Rust part moderate (03 §5). A DX row was added (07 §7). 07's flip criterion is quoted in full in §1.2 and §2 row 1. D1 is a decision for now, and the spike validates it. M1's suggested fix made Rust exposure the deciding factor. After the owner's clarification, career value is only a minor note that decides nothing. Security is even once Electron's cadence is kept, and every other evidence criterion favours Electron. The default is therefore **Electron**. The flip conditions to Tauri are: the cadence commitment fails, the Linux update-signature gap cannot be closed, or size/RAM becomes a requirement. The TL;DR, §1.2, §1.4, §1.5, §2 rows 1 and 5, §3.8, §3.10, D1, D8, §5, §6, §7, §8 F-2, §9, the Risks and the README were updated to match. |
| M2 | Applied | Closed-source Windows signing is now ≈ 120 (Artifact Signing) or ≈ 300–500 (OV, 04 §7). Certum's Open Source variants are restricted to open-source apps (01 §4b). The closed total is ≈ 220–600 (≈ 900 with Sentry Team). D2's saving is US$120–500 in signing plus up to US$312 for Sentry (07 §6). D3, §2 row 6, the TL;DR and the README were updated to match. |
| M3 | Applied (option a) | D6 now re-phases the contract. The harness phase Studio v1 depends on holds the read side plus `repos --json`, `daemon status --json`, `runs pause`, `runs drop` (with `derive-branch` if needed) and a global-stop verb (`runs stop-all`, which wraps the remote `stop`). Resume/answer come in v1.1 and review in v1.2. Option (b) is the named fallback if the act verbs slip. D6's size note now excludes `runs watch` from the 1–1.5k lines (05 lines 14, 217). D5, §1.3, §6 item 5, §7, §8 F-1, §9 items 7, 11–12 and 15, and the Risks were updated. Option (a) was chosen because (b) would undercut §1.3's "local runs are in v1 scope" argument. |
| S1 | Applied | §8 has a "Tracked in (per 11)" column for every row, and a "Step 0: check #170 and 11 first" procedure. H1/H1′ are not fixed by #170, and H1′ is partly covered by #318 Q2; the deny list feeds #318 Q1. 09-H6 folds into #309 (or #318 Q1), with #316's credential leg. The cargo cache is partly covered by #234 and now applies only if the pick flips to Tauri. 06-H3 is partly covered by #241. The §9 item now says to check first, file what is not covered, fold the rest into existing issues, and link them. The owner's spot-check of 11's two key claims is recorded. |
| S2 | Applied | (a) §8 is split into Part A, security findings ranked by severity (08's grades; the 09 rows are tagged [10's grading]), and Part B, features, contract work and documentation ranked by priority for Studio. The contract is no longer labelled High, and 08-H10 is shown as Low. The rows were renumbered S-1…S-13 and F-1…F-6, and every reference was updated. (b) The 08 Risk 1 contingency (H1/H1′ drop to Info if every write is refused) was added to D5, S-1, §6 item 11, §9 item 14, the TL;DR, the Risks and the README. |
| S3 | Applied | New §3.0, from 01 Q1. |
| S4 | Applied | Added to §3.1 (03 §4, 06 §2.6: 38–63 / 33–53 O-d, summarised as 33–63). |
| S5 | Applied | Days 1 and 2 are now 1.5 days each. The spike is ≈ 7 O-d plus 0.5 optional, or 7–8 with Day 0 admin. The argv fuzz is scheduled on Day 4. A hardware list says which tests drop without each machine. The 60% carry-over is tagged [inferred] (≈ 4 O-d) and credited in §7 (spike + v1 ≈ 36 O-d on Electron). The spike was also refocused on validating Electron: updater signature hook, fuses, CDP. A thin Tauri comparison is now optional. |
| S6 | Applied | The flip conditions moved to §1.2, after "Reading". §3.4 and the references now point there. The conditions now flip from Electron to Tauri (see M1). |
| S7 | Applied | (a) Row for 11 added, verdict "Not reviewed". (b) The 10 row now reads "PASS WITH FIXES · review", and the header status is reviewed. (c) The suggested "Rust exposure" flip condition was superseded by the owner clarification: the README now lists the evidence-based flip conditions to Tauri. (d) The cost bullet was fixed. |
| S8 | Applied | §3.3 and §3.10 both use 03 §5's wording: moderate (Android and JVM back-end), desktop Compose niche. |
| N1 | Applied | The process note was deleted from §2 row 1. |
| N2 | Applied | §9 item 5 now gives the run titles `harness <action> <branch>` (`run`, `pause`, `warm`, `stop`). |
| N3 | Applied | §6 item 2 cites 08 §6.2 item 8 against §4.1 row 13 for the Tauri isolation pattern, now in the Tauri bracket. |
| N4 | Applied | The TL;DR and §3.8 name the desktop-shell suites (08 §4.3 #1, #2, #5) and say that the DNS-rebinding suite (#3) applies only to the local web modes. |
| N5 | Applied | Bundle row: "Linux AppImage 70 MB+" (04 §5). |
| N6 | Applied | §3.2 uses 02's ranges (Tauri 88–109 MB macOS, ≈ 94 Linux, ≈ 312 Windows; Electron ≈ 128–600 MB; benchmarks disagree by 2–4×). |
| N7 | Applied | §3.9 carries 09's grades: [unambiguous] for own `claude -p`, [strong reading] for the carve-out, and [ask] for sustained unattended use (email item b). |
| N8 | Applied | D11 added (React or Svelte), deferred to spike Day 1. |
| N9 | Applied | §9 item 6: treat run logs on public repos as public (08 H3, Risk 3); prefer the committed analytics summary. |

### Post-resolution note (2026-11-12)

The 13 proposed issues from `11-harness-findings-vs-issue-170.md` were filed on devscene as #344–#356, at the owner's request. The fixes are worded as proposals to re-verify against the code. File 11 was then removed. §8, §9 and the README now point at those issues. The references to file 11 above are kept as a record of the review.
