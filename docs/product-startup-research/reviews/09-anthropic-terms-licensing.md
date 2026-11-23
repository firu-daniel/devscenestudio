# Review — 09-anthropic-terms-licensing.md
> Reviewer verdict: PASS WITH FIXES · Date: 2026-11-12

## Summary

I re-fetched every quoted clause live on 2026-11-12. The quotes are exact and current. That covers the Claude Code legal-and-compliance page, the authentication, GitHub Actions, CLI reference and Agent SDK pages, the Consumer Terms (EEA version), the Usage Policy, the Trademark Guidelines, the Commercial Terms, both help-centre notices, `LICENSE.md` and npm. The harness-side claims also check out against `/Users/daniel/Work/devscene`. The core conclusion is sound: Claude can be used in the harness, and the API-key path is never in doubt.

The fixes are about calibration and about reassuring the owner where the text supports it:
- Two items are graded more certain than the text supports: teammates triggering runs on one person's token, and descriptive naming.
- One item is graded more alarming than it needs to be: the subscriber's own headless use.
- The required US/EEA "non-commercial" comparison was not done. It is done below.
- Some counter-evidence and timeline nuance is missing.

## What I verified as correct (no change needed)

- **Legal page [1].** All quoted sentences are verbatim and current:
  - the "Can customers offer Claude Code" conditions
  - the name-and-logo paragraph
  - "OAuth authentication is intended exclusively for purchasers of Claude Free, Pro, Max, Ultra, Team, and Enterprise…"
  - the "Developers building products…" paragraph
  - the "unmodified Claude Code binary" carve-out
  - "without prior notice"
  - "contact sales"
- **Authentication [2].** The `setup-token` paragraph is verbatim: "For CI pipelines, scripts, or other environments where interactive browser login isn't available, generate a one-year OAuth token with `claude setup-token`" and "requires a Pro, Max, Ultra, Team, or Enterprise plan". The precedence ranks are correct (API key 3, OAuth token 5, "-p … always used when present"). Bare mode does not read `CLAUDE_CODE_OAUTH_TOKEN`. The credential paths, including the macOS Keychain fallback, are correct.
- **GitHub Actions [4].** The secret descriptions, including "Pro, Max, Ultra, Team, and Enterprise", the "secret shared across repositories" sentence, the cost sentence and WIF are all verbatim. `/install-github-app` does offer "creating a long-lived token with your Claude subscription" and saves it as `CLAUDE_CODE_OAUTH_TOKEN`.
- **CLI reference [10].** `claude setup-token`: "Generate a long-lived OAuth token for CI and scripts." `claude auth status` wording is verbatim.
- **Help centre [8]** (https://support.claude.com/en/articles/15036540). Both notices exist:
  - **June 15, 2026:** "We've paused the previously-announced changes to Claude Agent SDK usage." … "Claude Agent SDK, `claude -p`, and third-party app usage still draw from your subscription limits."
  - **October 7, 2026:** "Claude Max, Ultra, and Team plans now include monthly API credits" (API-key usage from a linked Console org). "when you're signed in with your Claude plan, the Claude Agent SDK and `claude -p` still draw from your subscription limits."
  - The page gives no dollar amounts and does not mention GitHub Actions.
- **Ultra exists.** It costs $200/month and includes Claude Code (https://claude.com/pricing). Help article 11145838 is now titled "Use Claude Code with your Pro, Max, or Ultra plan".
- **Consumer Terms [3].** I extracted these from the page HTML:
  - §2 account sharing and §3 automated access are verbatim.
  - §13 "Use of our brand" is verbatim.
  - The effective date is Oct 8, 2025, and the contracting party is Anthropic Ireland, Limited.
- **Usage Policy [6].** It is effective **Nov 12, 2026** (it changed today), and both quoted prohibitions are verbatim. **Trademark Guidelines [5].** Effective 2024-08-01, and all four quotes are verbatim. **Commercial Terms [16].** Effective 2025-06-17. D.4 reads "resell the Services except as expressly approved by Anthropic".
- **Agent SDK branding [7].** It is verbatim, and the Commercial-Terms governance statement is present.
- **Claude Code licence.** `LICENSE.md` reads "© Anthropic PBC. All rights reserved. Use is subject to Anthropic's Commercial Terms of Service." npm reports `2.1.322`, modified 2026-11-10, with licence `SEE LICENSE IN README.md`.
- **Issue #24600.** Closed as NOT_PLANNED on 2026-03-11 by the inactivity bot, with no Anthropic answer.
- **Harness claims:**
  - `devscene-run.yml` 792–799 has the unpinned `npm install -g @anthropic-ai/claude-code`, run only when `claude` is absent. Lines 804–808 and 1015–1020 hold the credential check and export. `devscene-control.yml` 337–344 and 382–383 (`issue_comment` only) match.
  - `cli/templates/claude/settings.autonomous.json` `sandbox.credentials.envVars` denies `ANTHROPIC_API_KEY` and `CLAUDE_CODE_OAUTH_TOKEN` (lines 150–151). `files` does **not** list `~/.claude/.credentials.json`, which confirms H6.
  - No code under `cli/src`, `cli/templates` or `plugin` reads `.credentials.json`.
  - `docs/remote-execution.md` §9 cites sources "retrieved 2026-09-24 (… not re-fetched)", which confirms H1.
  - `doctor --check-github` (`cli/src/doctor/checks.ts` ~3235–3250) warns about `*` combined with the OAuth token, and about writers outside the list while the token is set.
  - The LICENSE is Apache-2.0 and NOTICE carries the copyright.

## Must fix

**M1. Teammates triggering runs on one person's token is graded [unambiguous]. It should be [strong reading].**
*Where:* TL;DR bullet 4, F4 "Only the subscriber's own runs may use it [unambiguous]", Answer 3.

*Problem:* The Consumer Terms clause ("make your Account available to anyone else") is unambiguous text, but applying it to "a teammate's action starts a CI job on my token" is an inference. Anthropic's own GitHub Actions doc and app point the other way and are not mentioned:
- `/install-github-app` offers to mint a subscription token and store it as a repo secret.
- `claude-code-action` then lets **any user with write access** trigger runs with `@claude` ("Who can trigger runs → Write access").

The only Anthropic text on point is the hint that an OAuth token "is tied to the subscription of the person who ran `claude setup-token`". That sentence appears under "Set up for an organization", for secrets shared across repositories.

*Evidence:* https://code.claude.com/docs/en/github-actions ("Quick setup", "Who can trigger runs", "Set up for an organization"); https://www.anthropic.com/legal/consumer-terms §2.

*Fix:* Regrade to **[strong reading]** and add the counter-evidence. Suggested TL;DR text:

> "A subscription token is meant for the subscriber's own runs. Letting teammates start runs on it most plausibly conflicts with Consumer Terms §2 ('make your Account available to anyone else') and with Anthropic's own advice to use an API key for shared secrets [3, 4]. Anthropic's `claude-code-action` does, however, let any repo writer trigger runs on whatever token is installed, so the text is not explicit about this case. **[strong reading]**. Use an API key or Team/Enterprise for team repos, and add this to the email to Anthropic."

Add an item **(d)** to the Answer 8 email: "may collaborators trigger CI runs that use the repo owner's `CLAUDE_CODE_OAUTH_TOKEN`?"

**M2. The US vs EEA "Non-commercial use only" comparison is missing. The dispatch required it.**
*Where:* F7 last row, Answer 6, Risks ("This was not compared").

*Findings:*
- **EEA/CH version** (served at https://www.anthropic.com/legal/consumer-terms from both my fetch locations). The contracting party is Anthropic Ireland, Limited, effective Oct 8, 2025. The clause sits in **§11 "Disclaimer of warranties, limitations of liability, and indemnity"**: *"**Non-commercial use only.** You agree that you will not use our Services for any commercial or business purposes and we and our Providers have no liability to you for any loss of profit, loss of business, business interruption, or loss of business opportunity."* [verified, page HTML]. The same terms say they apply to "a consumer who is resident in the European Economic Area or Switzerland. You are a consumer if you are acting wholly or mainly outside your trade, business, craft or profession" [verified].
- **US / rest-of-world version** (Anthropic, PBC). I could not fetch it live: the page is geo-served and both WebFetch and curl received the Ireland text. The archived copies at `anthropic.com/legal/archive/<id>` are EEA or older UK versions. Two secondary sources say the US text has **no blanket clause**, only *"Use of our Services for evaluation purposes are for your personal, non-commercial use only"*. Those sources are an HN thread quoting both texts (https://news.ycombinator.com/item?id=46595957) and a blog updated 2026-10-26 (https://autonomee.ai/blog/claude-code-terms-of-service-explained/). Grade: **[secondary]**.

*Why it matters, and why it should be framed calmly:*
- The clause governs **which Anthropic plan an EEA/Swiss professional should use**, not whether DevScene may drive Claude. It reads mainly as a liability limit, and its own "consumer" definition makes it unclear whether a professional using Pro/Max for work is a "consumer" under these terms at all.
- It bites EEA users of DevScene on Pro/Max/Ultra doing paid work. If the owner is EEA-resident, it also bites the owner's own Pro/Max/Ultra use while building DevScene as a business.
- The API key (Commercial Terms) and Team/Enterprise avoid it entirely.

*Fix:*
- Replace the Risks bullet with the findings above.
- Promote a one-line version to the TL;DR, graded **[ask]**: "EEA/Swiss consumer terms say Pro/Max/Ultra are not for commercial or business use. The US terms reportedly don't [secondary]. EEA professionals, possibly including the owner, should use an API key or a Team plan, or get confirmation. This is about plan choice, not about whether the harness may use Claude."
- Add it as item (e) to the Anthropic email, and keep "ask a lawyer".

**M3. Descriptive naming is graded [unambiguous]. It is [strong reading], and the file contradicts itself.**
*Where:* TL;DR bullet 5 ("Plain-text accurate statements such as 'runs Claude Code' are allowed [1] … **[unambiguous]**"), Answer 4.

*Problem:* The plain-text permission sits inside the legal page's "Can customers offer Claude Code in their products?" section, which addresses businesses preinstalling Claude Code under the Commercial Terms. DevScene is not that customer. The Trademark Guidelines say *"You may only use our trademarks as specifically permitted by us and only in materials we approve beforehand"*, and they contain no nominative-use rule. Consumer Terms §13 requires written permission for use "in connection with products or services other than the Services". F5 itself grades the descriptive use [strong reading], and Answer 8(c) lists it as an [ask]. The TL;DR [unambiguous] conflicts with both.

*Evidence:* https://code.claude.com/docs/en/legal-and-compliance, https://www.anthropic.com/legal/trademark-guidelines.

*Fix:* Split the grade:
- "Never in a product, feature or company name or logo, and no Anthropic logos without written permission: **[unambiguous]**."
- "Plain-text 'works with / runs Claude Code' in body text: **[strong reading]**. Anthropic allows this wording for products that preinstall Claude Code, and it is ordinary descriptive use. Confirm in the email (c)."

**M4. The top of the file must say clearly what is not in doubt. The subscriber's own headless use is under-graded.**
*Where:* TL;DR bullets 1–3, Answer 1.

*Problem:* The owner's worry is "may I use Claude in the harness at all?". The file never says plainly that the worst case of the one open [ask] is a change of credential type, not a ban. It also grades the subscriber's own `claude -p` / `setup-token` use as [strong reading], although Anthropic's docs **explicitly** permit it. The Consumer Terms exception is "where we otherwise explicitly permit it", and the docs say generate a subscription token "For CI pipelines, scripts, or other environments" [2]. The CLI reference says "for CI and scripts" [10]. The help centre says plan sign-in `claude -p` "still draw[s] from your subscription limits" [8]. That meets the exception's own test.

*Fix:* Open the TL;DR with a three-line box:

> **Not in doubt:**
> (1) Running the harness with an Anthropic API key, or Bedrock/Vertex/Foundry: **[unambiguous]**.
> (2) A subscriber running the stock `claude -p`, locally or in their own CI with their own `setup-token` token: explicitly documented, **[unambiguous]**.
> (3) DevScene/Studio never touching credentials, only spawning the user's CLI: matches the legal page's carve-out, **[strong reading]**.
>
> **The one open point** is whether a third-party tool that orchestrates `claude -p` should steer users to API keys ([ask], F2). If Anthropic says yes, users switch credential type. Nothing in the terms suggests the harness may not use Claude.

Then regrade TL;DR bullet 2 and Answer 1 to match: (2) is [unambiguous], and the tool layer is [strong reading]/[ask].

## Should fix

**S1. The [ask] is missing two pieces of counter-evidence (F2, last paragraph).** Add them so the [ask] is honestly motivated and stays an [ask], not an alarm:
- The Agent SDK overview says *"To drive the same agent loop from a language other than Python or TypeScript, run the CLI as a subprocess with the `-p` flag and `--output-format json`"*. Anthropic itself thus presents spawning `claude -p` as the Agent SDK's equivalent, which strengthens the reading that the "Developers … including those using the Agent SDK, should use API key authentication" sentence can reach CLI-wrapping tools.
- The SDK note reads *"Unless previously approved, Anthropic does not allow third party developers to offer claude.ai login **or rate limits** for their products"*. The file omits "or rate limits".

On the reassuring side, add that the June 15 help-centre notice says Agent SDK, `claude -p` "and third-party app usage still draw from your subscription limits".

Evidence: https://code.claude.com/docs/en/agent-sdk/overview, https://support.claude.com/en/articles/15036540.

**S2. The 2026 timeline contradicts itself and does not say what was superseded.**
- The 2026-04-04 bullet says subscription limits stopped covering third-party harnesses. The June 15 notice (quoted in F2) says "third-party app usage still draw from your subscription limits", and the page does not define "third-party app". Say that the two are unreconciled.
- The 2026-02 Register quote ("in any other product, tool, or service — including the Agent SDK — is not permitted") **no longer appears** on today's legal page. Today's help centre counts plan-sign-in Agent SDK usage against subscription limits. Add "superseded by today's text [1, 8]" so the owner does not read the February wording as current.

Evidence: https://www.theregister.com/2026/02/20/anthropic_clarifies_ban_third_party_claude_access; https://code.claude.com/docs/en/legal-and-compliance.

**S3. Timeline citations overstate.**
- "2026-01-09: OpenCode, Cline, RooCode and OpenClaw broke [11, 12]": the Register [11] confirms only OpenCode (removed support after "anthropic legal requests"). The four-tool list and the 2026-01-09 date come from falcao.org [12], which also reports Anthropic's legal demands to OpenCode on 2026-03-19. Cite [12] for these and add the March item.
- "Announced for 2026-06-15 … [8, verified]": [8] confirms only that "previously-announced changes" were paused. The content (announced 2026-05-13; $20 Pro / $100 Max 5x / $200 Max 20x monthly credits for programmatic use) is falcao.org [secondary]. Change the tag. This also corrects H1: the figures can be **re-sourced** as "announced, then paused" [secondary] rather than dropped.
- Source 12's thenewstack URL returns 403 today. Mark it as unavailable.

Evidence: https://falcao.org/posts/anthropic-claude-access-crackdown-ecosystem-fallout/, https://lilting.ch/en/articles/anthropic-claude-code-openclaw-third-party-paygo.

**S4. One quote is attributed to the wrong section (F2 table, row 5).** "Advertised usage limits for Pro, Max, and Ultra plans assume ordinary, individual usage…" sits under the legal page's **"Usage policy › Acceptable use"**, not "Authentication and credential use". The "without prior notice" sentence is in the authentication section. Split the row.

**S5. The container claim lumps two different things together (F6 row 2, H3).** "Publish a Docker image **or devcontainer** with Claude Code preinstalled → No" is right for a **pre-built, published image**. A `devcontainer.json`/Dockerfile that installs Claude Code at build time on the user's machine is a different case. Anthropic ships an official Dev Container Feature (`ghcr.io/anthropics/devcontainer-features/claude-code`) and documents `npm install -g @anthropic-ai/claude-code@X.Y.Z` in a Dockerfile. That is the same pattern as the workflow step the file already rates as fine.

Fix: "A pre-built image pushed to a registry with Claude Code inside: No, unless Commercial Terms [strong reading]. A devcontainer definition or Dockerfile in the repo that installs it at build time: Fine [strong reading], as Anthropic's own feature does." The same page also supports H2's pinning suggestion (`@X.Y.Z` plus `DISABLE_AUTOUPDATER`). Evidence: https://code.claude.com/docs/en/devcontainer.

**S6. Two documents name different terms for Claude Code (F6, TL;DR bullet 6).** `LICENSE.md` says use is "subject to Anthropic's **Commercial** Terms". The legal page says Free/Pro/Max/Ultra users are under the **Consumer** Terms. Note this in one line and say the legal page's per-plan split governs. The redistribution conclusion ("All rights reserved", so no bundling) does not change.

**S7. The PyQt6 wording is imprecise (F8 table, TL;DR bullet 8, Answer 7).** "Not compatible with PyQt6" and "the distributed app becomes GPLv3" need the nuance. Apache-2.0 code may be combined into a GPLv3 work. Studio's own source files can stay Apache-2.0, but the **distributed combined app** must be offered under GPLv3, unless the owner buys a commercial PyQt licence. Riverbank's FAQ says: "If your license is incompatible with the GPL then you need a commercial PyQt license." Suggested text: "PyQt6 (GPLv3/commercial): the shipped app must be GPLv3 (sources may stay Apache-2.0), or buy a commercial PyQt licence."

Evidence: https://www.riverbankcomputing.com/commercial/license-faq. The Slint row is correct: Royalty-free, GPLv3 or commercial, and "your own files can stay MIT or Apache-2.0" (Slint `LICENSE.md`).

**S8. The SignPath quote is wrong (F8 last bullet).** The live text is *"The project must use an OSI-approved Open Source license without commercial dual-licensing for all components"* and *"The project may not contain any proprietary, non open-source component"*. The file's *"without dual licensing"* is not the wording. The conclusion holds and is stronger than stated: proprietary pro features in the same project would also break eligibility. Note that the page is marked draft. Evidence: https://signpath.org/terms.

**S9. H1 should cover more of §9's drift.**
- §9 says `CLAUDE_CODE_OAUTH_TOKEN` is documented "on the Pro, Max, Team and Enterprise plans". Today's docs add **Ultra**.
- §9 says the paused change covered "GitHub Actions", but the help-centre page does not mention GitHub Actions.

Add both to H1 (`docs/remote-execution.md` line 867 and the "A paused billing change" paragraph).

**S10. H5 / F4 overstate how far the doctor protects against the teammate case.** `doctor --check-github` warns only for `*` with the OAuth token, and for writers **outside** the list. A list that names several teammates while the owner's `CLAUDE_CODE_OAUTH_TOKEN` is set gets only a note (`checks.ts` ~3227–3250). That is exactly the teammate case. Say so, and suggest a warning when an OAuth token is set and `DEVSCENE_RUN_ACTORS` names more than one login.

## Nice to have

**N1. Qt (F8).** "Qt/PySide6 LGPL, fine with dynamic linking" holds for the Qt Essentials. Some Qt add-on modules are licensed GPLv3/commercial only, not LGPL. Add "check each module's licence at qt.io before using add-ons". This is reviewer knowledge, not re-fetched.

**N2. F1 row 4.** "`docs/remote-execution.md` §'4. Set a credential secret'" is **§7, step 4** (around line 502). The file's own §4 is a different heading.

**N3. F1 row 1.** `autonomous-watcher.sh` line 1375 is a comment that describes the launch, not the launch itself. Cite it as such, or cite the actual invocation.

**N4. F3 item 1, checklist, H6.** `CLAUDE_CONFIG_DIR` moves `.credentials.json`, and keys the macOS Keychain entry, to another directory (authentication doc, "Credential management"). Studio's watcher exclusion and the H6 deny entry should match `**/.credentials.json` under any configured config directory, not only `~/.claude`.

**N5. F6 "Studio runs Anthropic's official installer on click → Probably fine [ask]".** This is slightly more alarming than the text supports. The user installs from Anthropic's channel on their own machine, and nothing is preinstalled "in your products". [strong reading] is enough. Keep "prefer link + copy button" as a UX preference.

**N6. Heavy-use row (F2).** Add that verified Ultra accounts have no five-hour limit, only a weekly one (help article 11145838). This is relevant to "many parallel runs".

**N7. Policy volatility.** Note that the Usage Policy took effect **today** (2026-11-12). That supports the quarterly re-check advice.

## Sources checked (all 2026-11-12)

- https://code.claude.com/docs/en/legal-and-compliance
- https://code.claude.com/docs/en/authentication
- https://code.claude.com/docs/en/github-actions
- https://code.claude.com/docs/en/cli-reference
- https://code.claude.com/docs/en/agent-sdk/overview
- https://code.claude.com/docs/en/devcontainer
- https://support.claude.com/en/articles/15036540
- https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan
- https://claude.com/pricing
- https://www.anthropic.com/legal/consumer-terms (EEA version, HTML extracted)
- https://www.anthropic.com/legal/archive/* (7 archived versions, none of them the current US text)
- https://www.anthropic.com/legal/aup
- https://www.anthropic.com/legal/trademark-guidelines
- https://www.anthropic.com/legal/commercial-terms
- https://news.ycombinator.com/item?id=46595957
- https://autonomee.ai/blog/claude-code-terms-of-service-explained/
- https://www.theregister.com/2026/02/20/anthropic_clarifies_ban_third_party_claude_access
- https://falcao.org/posts/anthropic-claude-access-crackdown-ecosystem-fallout/
- https://lilting.ch/en/articles/anthropic-claude-code-openclaw-third-party-paygo
- thenewstack (403)
- `gh api repos/anthropics/claude-code/contents/LICENSE.md`
- `npm view @anthropic-ai/claude-code`
- `gh issue view 24600`
- https://signpath.org/terms
- https://www.riverbankcomputing.com/commercial/license-faq
- Slint `LICENSE.md`
- Harness repo files listed under "What I verified"

## Review resolution

Resolved 2026-11-12 by the fix agent. Every factual correction was re-checked live (legal-and-compliance, authentication, github-actions, agent-sdk/overview, devcontainer, help-centre 15036540 and 11145838, consumer-terms, The Register, falcao.org, autonomee.ai, HN 46595957, Riverbank FAQ, signpath.org/terms) or against `/Users/daniel/Work/devscene` (`checks.ts`, `autonomous-watcher.sh`, `docs/remote-execution.md`) before it was applied.

| ID | Resolution |
|---|---|
| M1 | **Applied.** Teammate case regraded to [strong reading] in TL;DR, F4 and Answer 3, with the `/install-github-app` and "Who can trigger runs → write access" counter-evidence (both re-verified). Added as email item (d). Also cited the legal page's "customer's own authorized users" sentence for API keys. |
| M2 | **Applied.** EEA §11 clause, heading, contracting party and "consumer" definition re-verified live. US version still not fetchable (geo-served); kept [secondary] with the HN thread (flagged as ~10 months old) and the autonomee.ai blog (confirmed it says only the EEA/Swiss version carries the clause; it does not itself quote the "evaluation purposes" sentence, which comes from HN). New F7 comparison, TL;DR bullet, Risks bullet, email item (e). |
| M3 | **Applied.** Naming split: name/logo/no-logos [unambiguous]; plain-text descriptive use [strong reading], with the Commercial-Terms-customer context noted. TL;DR, F5 and Answer 4 now agree. Email item (c). |
| M4 | **Applied.** File opens with a "Not in doubt / Open questions" box: API key [unambiguous], subscriber's own `claude -p` / `setup-token` [unambiguous], spawn-only design [strong reading]; three narrow open questions, each with its worst case (credential type or plan change, not a ban). TL;DR bullet 2, F2 assessment and Answer 1 regraded to match. |
| S1 | **Applied.** Both Agent SDK quotes ("run the CLI as a subprocess…", "claude.ai login or rate limits") verified verbatim and added to F2, plus the reassuring June 15 "third-party app usage" sentence. |
| S2 | **Applied.** Timeline marks the February Register wording as superseded (confirmed absent from today's legal page) and states the April 4 vs June 15 "third-party app" contradiction as unreconciled. |
| S3 | **Applied.** 2026-01-09 tool list now cited to falcao.org [12]; The Register confirmed to name only OpenCode's case. Added the 2026-03-19 item; noted that The Register (2026-02-20) already reports an OpenCode commit citing "anthropic legal requests", so the two sources disagree on the date. 2026-05-13 credit figures re-sourced to [12, secondary]; thenewstack marked 403/unavailable; H1 now re-sources rather than drops the figures. |
| S4 | **Applied.** Verified: "ordinary, individual usage" sits under "Usage policy › Acceptable use"; "without prior notice" under "Authentication and credential use". Row split. |
| S5 | **Applied.** Dev Container Feature, pinned `@X.Y.Z` Dockerfile install and `DISABLE_AUTOUPDATER` verified. F6 splits pre-built image (No) from build-time devcontainer/Dockerfile (Fine [strong reading]); H2 and H3 updated. |
| S6 | **Applied.** One-line note in F6: `LICENSE.md` says Commercial Terms, legal page's per-plan split governs; redistribution conclusion unchanged. |
| S7 | **Applied.** PyQt6 wording fixed in TL;DR, F8 and Answer 7; Riverbank FAQ sentence verified verbatim. |
| S8 | **Applied.** SignPath quotes corrected verbatim (both conditions verified; page marked draft); conclusion strengthened to cover proprietary pro features. |
| S9 | **Applied.** H1 lists the missing Ultra (line ~867 verified) and the unsupported "GitHub Actions" in the paused-change paragraph (help centre verified not to mention it). |
| S10 | **Applied.** Verified in `checks.ts` (~3224–3250): a multi-login list with the OAuth token set yields only a note. F4 and H5 now say the guard is partial and suggest a warning for more than one login. |
| N1 | **Applied** as advice ("check each module's licence at qt.io"), tagged [inferred] since not re-fetched. |
| N2 | **Applied.** Verified: §7 "Turning it on", step 4 at line 503. |
| N3 | **Applied.** Verified: line 1375 is a comment; the real launch is the `exec "$launch_agent_cli" -p …` invocation around lines 3640–3647. F1 cites both. |
| N4 | **Applied.** `CLAUDE_CONFIG_DIR` behaviour verified in the authentication doc; F3 item 1, the checklist and H6 now cover any configured config directory. |
| N5 | **Applied.** Installer-on-click regraded to Fine [strong reading]; link plus copy-button kept as a UX preference. |
| N6 | **Applied.** Verified Ultra "don't have a five-hour session limit" added to the F2 limits row and heavy-use row. |
| N7 | **Applied.** Usage Policy effective date (today) noted in F2 and in the volatility risk. |

Also added: a consolidated "Draft email to Anthropic" section covering every [ask] item (a–f), and `Status: reviewed` in the header. The harness-owned section remains separate.
