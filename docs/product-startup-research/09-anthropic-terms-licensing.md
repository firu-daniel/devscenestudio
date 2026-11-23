# 09 — Anthropic terms, trademark and licensing check (Issue #1 item 16)

> Status: reviewed · Date: 2026-11-12 · Area owner: research agent · Review: `reviews/09-anthropic-terms-licensing.md` (all findings resolved there)
>
> **Not legal advice.** This file reads Anthropic's published terms and docs as of 2026-11-12. Each answer is graded **[unambiguous]** (the text says it directly), **[strong reading]** (several primary texts point the same way, but none names this exact case) or **[ask]** (the owner should get written confirmation from Anthropic or advice from a lawyer). Confidence tags from the brief ([verified], [secondary], [inferred]) are used for sources.

> **Not in doubt**
> 1. **Running the harness with an Anthropic API key** (or Bedrock, Vertex or Foundry credentials). This is the Consumer Terms' own exception, and the Commercial Terms cover it [1, 3]. **[unambiguous]**
> 2. **A subscriber running the stock `claude -p` with their own Pro/Max/Ultra login**, locally or in their own CI with their own `claude setup-token` token. Anthropic documents this explicitly ("for CI pipelines, scripts, or other environments" [2]; "for CI and scripts" [10]), and its help centre counts plan sign-in `claude -p` use against subscription limits [8]. That is the "where we otherwise explicitly permit it" exception in Consumer Terms §3 [3]. **[unambiguous]**
> 3. **DevScene and Studio never touching credentials, only spawning the user's own unmodified CLI.** This matches the legal page's carve-out for "an end user … signing in to the unmodified Claude Code binary with their own Claude subscription" [1]. **[strong reading]**
>
> **Open questions (narrow; all go in one email, see "Draft email to Anthropic")**
> - (a) Does a tool that only spawns the user's stock `claude -p` count as one of the "products or services that interact with Claude's capabilities", which "should use API key authentication" [1]? **Worst case:** DevScene's docs steer users to API keys instead of subscriptions.
> - (b) May teammates trigger CI runs that spend one person's subscription token? **Worst case:** team repos use an API key, WIF or Team/Enterprise seats. The harness already supports all three.
> - (c) EEA/Swiss Consumer Terms say Pro/Max/Ultra are not for "commercial or business purposes" [3]. **Worst case:** EEA professionals, possibly including the owner, use an API key or a Team plan for paid work.
>
> In every case the worst outcome is **a change of credential type or plan, not a ban**. Nothing in Anthropic's terms suggests the harness or Studio may not use Claude.

## TL;DR

- **The core model is within the terms.** DevScene and Studio launch the user's own, unmodified `claude` binary, and that binary signs itself in with the user's own credential. That is the case Anthropic's legal page carves out: the restrictions do not *"prevent an end user from signing in to the unmodified Claude Code binary with their own Claude subscription"* [1]. What is prohibited is offering Claude.ai login, routing requests through other people's plan credentials, and collecting, storing or intermediating Claude.ai credentials or session tokens [1]. **[strong reading]** for the tool layer.
- **A subscriber's own headless use is documented and permitted.** The Consumer Terms bar automated access *"except when you are accessing our Services via an Anthropic API Key or where we otherwise explicitly permit it"* [3]. Anthropic explicitly documents `claude -p`, and `claude setup-token` *"for CI pipelines, scripts, or other environments"* [2]. Its help centre (notices of 2026-06-15 and 2026-10-07) says plan sign-in usage of `claude -p` and the Agent SDK *"still draw from your subscription limits"* [8]. **[unambiguous]**
- **The 2026 crackdown hit a different pattern.** The January–April 2026 enforcement hit tools that took subscription OAuth tokens and called the API with them outside Claude Code (OpenClaw, OpenCode and others) [11, 12]. DevScene never touches a token, so it is not that pattern. One narrow question remains: the legal page says developers of *"products or services that interact with Claude's capabilities … should use API key authentication"* [1]. Whether a tool that spawns the stock CLI counts is not addressed, and the `claude-code` docs issue asking that question was auto-closed for inactivity without an answer [13]. **[ask]** Worst case: steer users to API keys. Covered by the email.
- **GitHub Actions: `ANTHROPIC_API_KEY` and `CLAUDE_CODE_OAUTH_TOKEN` are both first-class, documented CI credentials** [4]. A subscription token is meant for the subscriber's own runs. Letting teammates start runs on it most plausibly conflicts with Consumer Terms §2 (*"make your Account available to anyone else"*) and with Anthropic's own advice to use an API key for shared secrets [3, 4]. Anthropic's `claude-code-action`, however, lets any repo writer trigger runs on whatever token is installed, so the text is not explicit about this case [4]. **[strong reading]** Use an API key, WIF or Team/Enterprise for team repos, and ask Anthropic (email item d).
- **Naming.** "Claude Code" or "Anthropic" must never appear in a product, feature or company name or in a logo, and Anthropic logos need written permission [1, 3, 5]. **[unambiguous]** Plain-text "works with / runs Claude Code" in body text: Anthropic allows this wording for products that preinstall Claude Code, and it is ordinary descriptive use [1]. **[strong reading]** Confirm in the email (item c). "DevScene", "DevScene Studio", ragscene, langscene, tracescene and scenewise are all clean of Anthropic marks.
- **Redistribution: none.** Claude Code's licence is *"© Anthropic PBC. All rights reserved. Use is subject to Anthropic's Commercial Terms of Service"* [9]. Studio must not bundle it, and the owner must not publish a pre-built image with it inside. The user installs it from Anthropic's channel, or the user's own CI runner or devcontainer build fetches it, as the harness does today. **[unambiguous]** for bundling, **[strong reading]** for build-time installs.
- **Monetisation.** Donations and a paid app tier are not restricted by Anthropic's terms as long as Studio never sells, bundles, pays for or proxies Claude usage. Hosting runs for users on the owner's infrastructure would change this: it would need the Commercial Terms plus the "customers offer Claude Code" conditions [1]. **[strong reading]**
- **EEA plan choice.** EEA/Swiss Consumer Terms say Pro/Max/Ultra may not be used *"for any commercial or business purposes"* [3, verified]. The US terms reportedly have no such blanket clause [20, 21, secondary]. EEA professionals, possibly including the owner, should use an API key or a Team plan, or get confirmation. This is about plan choice, not about whether the harness may use Claude. **[ask]**
- **Apache-2.0 for Studio** is compatible with every permissive framework in 01 (Electron, Tauri, Flutter, Compose, Wails, Avalonia). Qt/PySide6 (LGPL) are also fine with dynamic linking (check add-on module licences). PyQt6 (GPLv3/commercial): the shipped app must be GPLv3 (Studio's own sources may stay Apache-2.0), or the owner buys a commercial PyQt licence [22]. Obligations: ship LICENSE and NOTICE, and ship the third-party licence bundle (for Electron, that includes Chromium's licences). **[unambiguous]** for the licence texts, **[inferred]** for the packaging detail.

## Scope

This file covers Anthropic's Consumer Terms, Commercial Terms, Usage Policy, trademark guidelines, Claude Code legal/auth/GitHub Actions/Agent SDK/devcontainer docs, Claude Code's own licence, and Studio's outbound open-source licence. It defers code signing and the SignPath OSS condition to 01 and item 17, the GitHub API and data layer to 05, and the team-credential design to the harness's own `docs/team-accounts-research.md`.

## Findings

### F1. What the harness and Studio actually do (checked in the harness repo)

| Fact | Where | Terms relevance |
|---|---|---|
| Local runs: the watcher launches one headless `claude -p … --output-format stream-json` session per run | `cli/templates/scripts/autonomous-watcher.sh`: the launch is the `exec "$launch_agent_cli" -p "$launch_prompt" …` invocation (around lines 3640–3647); line 1375 is a comment that records a measured launch | Uses the user's installed CLI and its stored login |
| Remote runs: `devscene-run.yml` / `devscene-control.yml` read `secrets.CLAUDE_CODE_OAUTH_TOKEN` and/or `secrets.ANTHROPIC_API_KEY`, export only the non-empty ones to the harness step, and fail when neither is set | `devscene-run.yml` lines 804–808, 1015–1020; `devscene-control.yml` 382–383 (`issue_comment` only) | GitHub Actions credential model, see F4 |
| Remote runs install Claude Code on the runner with `npm install -g @anthropic-ai/claude-code` (unpinned), and only when `claude` is absent | `devscene-run.yml` 792–799; `devscene-control.yml` 337–344 | Fetched from Anthropic's npm package on the user's runner, so not redistribution (F6) |
| Setup docs tell the user to run `claude setup-token` and `gh secret set CLAUDE_CODE_OAUTH_TOKEN` by hand | `docs/remote-execution.md` §7 "Turning it on", step "4. Set a credential secret" (around line 503) | The token never passes through harness code. This is the right pattern |
| The sandbox profile denies `ANTHROPIC_API_KEY` and `CLAUDE_CODE_OAUTH_TOKEN` to sandboxed commands | `cli/templates/claude/settings.autonomous.json` lines 145–152 | Good hygiene. `.credentials.json` is **not** in the file deny list (H6) |
| No harness code reads `~/.claude/.credentials.json` or the Keychain (grep of `cli/src`, `cli/templates`, `plugin`) | — | Correct |
| Branding: "DevScene … an autonomous SDLC harness for Claude Code" in plugin.json, marketplace.json and README; topic `claude-code` in funding.json | — | Descriptive use, see F5 |
| Licence: Apache-2.0, with a NOTICE that asserts copyright | `LICENSE`, `NOTICE` | See F8 |

### F2. Subscription (Pro/Max/Ultra) versus API key for headless, automated use (Q1)

**What the texts say:**

| Source | Exact clause |
|---|---|
| Consumer Terms §3 (effective 2025-10-08) [3] | You may not use the Services: *"Except when you are accessing our Services via an Anthropic API Key or where we otherwise explicitly permit it, to access the Services through automated or non-human means, whether through a bot, script, or otherwise."* |
| Claude Code legal page, "Authentication and credential use" [1] | *"**OAuth authentication** is intended exclusively for purchasers of Claude Free, Pro, Max, Ultra, Team, and Enterprise subscription plans and is designed to support ordinary use of Claude Code and other native Anthropic applications."* |
| same [1] | *"**Developers** building products or services that interact with Claude's capabilities, including those using the Agent SDK, should use API key authentication through Claude Console or a supported cloud provider. Anthropic does not permit third-party developers to offer Claude.ai login into their own applications, or to route requests through Free, Pro, Max, or Ultra plan credentials on behalf of their users. Moreover, developers may not collect, store, or intermediate Claude.ai credentials or session tokens — sign-in to a Claude account must complete through Anthropic's own flow."* |
| same [1] | *"… Nor does it prevent an end user from signing in to the unmodified Claude Code binary with their own Claude subscription, including where a platform hosts Claude Code as described under Can customers offer Claude Code in their products? above."* |
| same [1] | *"Anthropic reserves the right to take measures to enforce these restrictions and may do so without prior notice."* |
| Claude Code legal page, "Usage policy › Acceptable use" [1] | *"Advertised usage limits for Pro, Max, and Ultra plans assume ordinary, individual usage of Claude Code and the Agent SDK."* |
| Authentication docs [2] | *"For CI pipelines, scripts, or other environments where interactive browser login isn't available, generate a one-year OAuth token with `claude setup-token`"* … *"This token authenticates with your Claude subscription and requires a Pro, Max, Ultra, Team, or Enterprise plan."* |
| CLI reference [10] | `claude setup-token`: *"Generate a long-lived OAuth token for CI and scripts."* |
| Help centre, "Use the Claude Agent SDK with your Claude plan" [8] | 2026-06-15: *"We've paused the previously-announced changes to Claude Agent SDK usage"*; Agent SDK, `claude -p` and *"third-party app usage still draw from your subscription limits."* 2026-10-07: Max, Ultra and Team plans *"now include monthly API credits"* for API-key usage from a linked Console organization, while *"when you're signed in with your Claude plan, the Claude Agent SDK and `claude -p` still draw from your subscription limits."* |
| Help centre, "Use Claude Code with your Pro, Max, or Ultra plan" [14] | *"Pro and Max plans have a five-hour session limit and a weekly limit."* *"Ultra plans have a weekly limit, and verified Ultra accounts don't have a five-hour session limit."* These limits are shared across Claude and Claude Code. It says nothing about CI, scripts or automation. |
| Usage Policy (effective **2026-11-12**, i.e. it changed today) [6] | Prohibits: *"Resell, proxy, or otherwise provide access to Claude through unauthorized means, including services that route requests through consumer subscriptions or misrepresent the product or client being used"* and *"Coordinate malicious activity across multiple accounts, or create multiple accounts, to avoid detection, circumvent product guardrails …"* |

**2025–2026 timeline** [secondary unless marked]:
- **2026-01-09:** server-side blocking of subscription OAuth tokens used outside Claude Code and Claude.ai. OpenCode, Cline, RooCode and OpenClaw broke [12, falcao.org]. The Register [11] confirms only OpenCode's case.
- **2026-02:** wording clarified. The Register (2026-02-20) reports compliance text: using Free/Pro/Max OAuth tokens *"in any other product, tool, or service — including the Agent SDK — is not permitted"*, and an Anthropic engineer citing *"unusual traffic patterns without any of the usual telemetry that the Claude Code harness provides"*. It also reports an OpenCode commit removing Claude support and citing "anthropic legal requests" [11]. **Superseded:** that sentence no longer appears on today's legal page [1, verified], and today's help centre counts plan sign-in Agent SDK and `claude -p` use against subscription limits [8, verified]. Do not read the February wording as current.
- **2026-03-19:** Anthropic's legal demands to OpenCode; OpenCode merges PR #18186 "anthropic legal requests" [12, falcao.org]. (The Register already reported a commit with that wording on 2026-02-20 [11]; the two sources disagree on the date.)
- **2026-04-04:** subscription limits stop covering third-party tools, which now need pay-as-you-go "extra usage"; one-time transition credits offered [12].
- **2026-05-13:** announced for 2026-06-15: monthly credits for programmatic use outside interactive Claude Code ($20 Pro, $100 Max 5x, $200 Max 20x) [12, falcao.org, secondary]. **Paused** on 2026-06-15 [8, verified: the page confirms only that "previously-announced changes" were paused, not their content].
- **2026-10-07:** monthly API credits added to Max/Ultra/Team for API-key usage. Plan sign-in usage is unchanged [8, verified].
- Today's legal page [1] is the current consolidated text. It contains the "unmodified binary" carve-out quoted above [verified].

**Unreconciled:** the 2026-04-04 change (third-party tools off subscription limits [12]) and the 2026-06-15 notice (*"third-party app usage still draw from your subscription limits"* [8]) point different ways, and the help centre does not define "third-party app". Neither changes DevScene's position, because DevScene runs the first-party CLI, but it shows how fast the wording moves.

**Assessment:**

| Pattern | Status |
|---|---|
| The user installs Claude Code and signs in through Anthropic's flow (`claude` / `claude auth login`), or sets their own `setup-token` token. They run the stock `claude -p` | **Permitted [unambiguous].** Explicitly documented for CI and scripts [2, 10], and counted against plan limits [8]. |
| DevScene or Studio spawns that same binary with `-p`, which uses the stored login | **Permitted [strong reading].** The stock binary does the auth, so it is "ordinary use of Claude Code" and keeps Anthropic's telemetry. The only open point is the "developers … should use API key" sentence below **[ask]**. |
| The same, with an API key in the user's environment | **Permitted [unambiguous].** This is the Consumer Terms exception, or the Commercial Terms for API users. |
| A tool that reads the user's OAuth token and calls the API itself (with any client other than the Claude Code binary) | **Prohibited [unambiguous].** "Collect, store, or intermediate". This is the 2026 crackdown pattern. |
| A tool offering "Sign in with Claude" in its own UI | **Prohibited [unambiguous].** |
| A product whose operator pays for or pools Claude usage for its users | **Prohibited [unambiguous].** "May not pay for, resell, or intermediate". |
| Very heavy unattended use on a Max/Ultra plan (many parallel runs, 24/7) | **Allowed but at risk [ask].** Limits *"assume ordinary, individual usage"*, and Anthropic may enforce *"without prior notice"* [1]. Verified Ultra accounts have no five-hour limit, only a weekly one [14], which suits many parallel runs better than Max. For sustained, high-volume or team use, recommend an API key. |

The one open point is the sentence *"Developers building products or services that interact with Claude's capabilities … should use API key authentication"* [1]. Read in context, it targets products that make their own API calls, like the Agent SDK. DevScene adds prompts and plugin assets to the user's own CLI session, as any Claude Code plugin does. Two texts make the question fair to ask rather than idle:
- The Agent SDK overview presents spawning the CLI as the SDK's equivalent: *"To drive the same agent loop from a language other than Python or TypeScript, run the CLI as a subprocess with the `-p` flag and `--output-format json`"* [7]. That supports reading the "including those using the Agent SDK" sentence as able to reach CLI-wrapping tools.
- The SDK note reads *"Unless previously approved, Anthropic does not allow third party developers to offer claude.ai login **or rate limits** for their products, including agents built on the Claude Agent SDK"* [7].

On the reassuring side: the 2026-06-15 notice says Agent SDK, `claude -p` *"and third-party app usage still draw from your subscription limits"* [8], and DevScene neither offers a login nor offers rate limits of its own; the user brings their own plan. The `claude-code` docs issue asking how CLI-wrapping projects are treated was auto-closed for inactivity on 2026-03-11 with no Anthropic answer [13]. **[ask]** The legal page itself invites the question: *"For questions about permitted authentication methods for your use case, please contact sales."* [1] If the answer is "use API keys", the remedy is a docs and default-credential change, not a redesign.

### F3. Does Studio's "spawn the user's CLI only" design avoid the third-party-login restrictions? (Q2)

Yes, provided it keeps these invariants **[strong reading]**. The legal page draws its line at the credential: a third party must not offer login, route requests, or *"collect, store, or intermediate Claude.ai credentials or session tokens"* [1]. Studio does none of these if it only spawns `claude`, `devscene`, `git` and `gh`, and reads harness files (`registry.json`, `status.json`, logs, analytics).

**Studio must never:**
1. Read, copy, parse, back up or sync `~/.claude/.credentials.json`, `%USERPROFILE%\.claude\.credentials.json`, the WSL copy under `\\wsl$\…\home\<u>\.claude\`, or the macOS Keychain entry Claude Code writes [2]. If `CLAUDE_CONFIG_DIR` is set, the CLI keeps `.credentials.json` under that directory instead and keys the Keychain entry to it [2], so the exclusion must match `**/.credentials.json` under any configured config directory, not only `~/.claude`. A "watch the whole config folder" implementation would read them by accident.
2. Offer "Sign in with Claude", embed Anthropic's OAuth page in a webview, or capture a login callback. *"Sign-in to a Claude account must complete through Anthropic's own flow"* [1].
3. Run `claude setup-token` and capture its stdout, for example to pipe it into `gh secret set` for the user. That makes Studio a collector or intermediary of a session token, even briefly. Instead, show the two commands and let the user run them in their own terminal, as the harness docs do.
4. Bundle, vendor or silently download Claude Code (F6), or patch it, wrap its network calls, set `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN` to a proxy it controls, or change the client identity. The Usage Policy bans services that *"misrepresent the product or client being used"* [6].
5. Store or display the values of `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN`, or set repo secrets on the user's behalf with values Studio has seen.
6. Rotate several accounts or subscriptions to stretch limits [6].
7. Embed an interactive Claude chat. This is already an Issue #1 decision, and it also keeps Studio clear of "alternative Claude Code frontend" questions [13].

**Studio may (low risk):**
- Run `claude --version` and `claude auth status` (*"Show authentication status as JSON … Exits with code 0 if logged in, 1 if not"* [10]) to colour a doctor icon. It should show only the `authMethod`/logged-in fields and must not log the email or organization unless the user asks.
- Tell the user to run `claude auth login` in their terminal, or open a terminal window with that command typed in. The flow is Anthropic's. **[strong reading]** Prefer instructions over automation.
- Show which credential type a repo's remote runs use, from secret **names** only (`gh secret list`; this needs admin access on the repo) or from `devscene doctor --check-github`.

### F4. GitHub Actions remote runs (Q3)

| Clause | Source |
|---|---|
| *"`ANTHROPIC_API_KEY`: a Claude API key from the Claude Console"*; *"`CLAUDE_CODE_OAUTH_TOKEN`: an OAuth token that authenticates with your Claude subscription, available on Pro, Max, Ultra, Team, and Enterprise plans. Generate one by running `claude setup-token` locally."* | [4] |
| Quick setup: `/install-github-app` offers *"creating a long-lived token with your Claude subscription"* and saves it as the repository secret `CLAUDE_CODE_OAUTH_TOKEN` | [4] |
| "Who can trigger runs": *"on issue and pull request events, the triggering user must have write access to the repository"* (no check of whose credential the run spends) | [4] |
| "Set up for an organization": *"For a secret shared across repositories, authenticate with an API key from the Claude Console rather than an OAuth token, since an OAuth token is tied to the subscription of the person who ran `claude setup-token`."* | [4] |
| *"If you authenticate with an OAuth token, runs use your Claude subscription instead of API billing."* | [4] |
| Workload identity federation (GitHub OIDC → Console service account) avoids storing a long-lived secret | [4] |
| Precedence: `ANTHROPIC_API_KEY` (rank 3) beats `CLAUDE_CODE_OAUTH_TOKEN` (rank 5); in `-p` mode *"the key is always used when present"*. Bare mode *"does not read `CLAUDE_CODE_OAUTH_TOKEN`"* | [2] |
| Consumer Terms §2: *"You may not share your Account login information, Anthropic API key, or Account credentials with anyone else or make your Account available to anyone else."* | [3] |
| Legal page: API keys may be configured *"for use by the customer's own authorized users"*, billed to the key owner | [1] |

**Assessment:**
- **A subscription OAuth token in CI, for the subscriber's own runs, is permitted [unambiguous].** Anthropic documents it [2, 4], and its own `/install-github-app` offers to create one and store it as a repo secret [4].
- **Teammates triggering runs on one person's subscription token: most plausibly not permitted [strong reading].** If a teammate starts a remote run (a label, a Studio "start", or an `@mention` handled by `devscene-control.yml`) and the run uses the owner's `CLAUDE_CODE_OAUTH_TOKEN`, that most plausibly "makes the account available" to someone else [3], and it runs against Anthropic's advice to use an API key when a secret is shared [4]. **Counter-evidence:** Anthropic's own quick setup installs a subscription token as a repo secret, and `claude-code-action` then lets any user with write access trigger runs on it [4]. The only Anthropic sentence on point sits under organization-wide secrets. So the text is not explicit. **[ask]** (email item d). Until answered: team repos belong on an API key (or WIF) under the Commercial Terms, which explicitly allow keys for "the customer's own authorized users" [1], or on Team/Enterprise seats. The harness already documents this split (`docs/remote-execution.md` §9).
- **What the doctor catches today.** `doctor --check-github` warns when `DEVSCENE_RUN_ACTORS` is `*` while `CLAUDE_CODE_OAUTH_TOKEN` is set, and when writers **outside** the list exist while that token is set. A list that names several teammates while the owner's token is set gets only a note (`cli/src/doctor/checks.ts` around 3224–3250). That is exactly the teammate case, so the guard is partial (H5).
- **Studio-specific consequence.** Issue #1 targets "team members whose repo someone else set up". When such a user drags a card to In Progress on a remote repo, Studio starts a run on someone else's credential. Studio should check (via `devscene doctor --check-github` or the harness's allow-list) that the current `gh` user may trigger runs, and say so before it dispatches. **[inferred]**

### F5. Naming and branding (Q4)

| Clause | Source |
|---|---|
| *"You can accurately say, in plain text, that your product has Claude Code preinstalled or that it runs Claude Code. But you can't use the Claude Code or Anthropic names or logos as part of your own product, feature, or company name, in your own logo, or in a way that suggests Anthropic built, endorses, or is partnered with your product. Any other use of Anthropic's names or logos is governed by our Trademark Guidelines and requires our written permission."* (This sits in the "Can customers offer Claude Code in their products?" section, which addresses businesses that preinstall Claude Code under the Commercial Terms.) | [1] |
| Agent SDK branding: allowed *"Claude Agent"*, *"Claude"* (inside an "Agents" menu), *"{YourAgentName} Powered by Claude"*; **not permitted** *"'Claude Code' or 'Claude Code Agent'"* and *"Claude Code-branded ASCII art or visual elements that mimic Claude Code"*; *"Your product should maintain its own branding and not appear to be Claude Code or any Anthropic product."* | [7] |
| Trademark Guidelines (effective 2024-08-01): *"You may only use our trademarks as specifically permitted by us and only in materials we approve beforehand."* … *"You may not use our trademarks in a manner that implies Anthropic's sponsorship or endorsement"* … *"No alterations of our trademarks … are permitted."* … *"Do not use a trademark symbol with the trademarks."* They contain no explicit nominative/descriptive-use rule. | [5] |
| Consumer Terms §13 "Use of our brand": *"You may not, without our prior written permission, use our name, logos, or other trademarks in connection with products or services other than the Services, or in any other way that implies our affiliation, endorsement, or sponsorship. To seek permission, please email us at marketing@anthropic.com."* | [3] |

**Assessment:**

| Use | Verdict |
|---|---|
| "Claude", "Claude Code" or "Anthropic" in a product, feature, company, repo-brand or logo name (e.g. "DevScene for Claude Code" as the *product name*, "Claude Runs" as a tab name) | **No [unambiguous]** |
| Plain-text descriptive phrases in a README, website body or store blurb: "runs your own Claude Code CLI", "works with Claude Code", "a harness for Claude Code" | **Yes [strong reading].** The legal page allows exactly this wording for products that run Claude Code, and it is ordinary descriptive use. But that permission is addressed to Commercial-Terms customers, and the Trademark Guidelines and §13 speak of prior permission, so confirm it (email item c). Keep it factual, in body text, not styled as a logo or badge. |
| "Powered by Claude" badge or tagline | **Avoid.** It comes from the Agent SDK rules, and DevScene does not use the Agent SDK. As a badge it is a logo-like use. **[ask]** if wanted (email item c). |
| Anthropic or Claude logos, the Claude sparkle mark, Claude Code's orange pixel mascot or ASCII banner, a "works with" logo strip on the product website | **No, without written permission** (marketing@anthropic.com) [1, 3, 5, 7] **[unambiguous]** |
| A visual identity that looks like Claude Code's (terracotta palette plus a pixel-art mascot, or a terminal-banner look) | **Avoid** ("not appear to be Claude Code") [7] |
| A ™ symbol after "Claude" | **No** (*"Do not use a trademark symbol"*) [5] |
| GitHub topic or npm keyword `claude-code`, the funding.json tag | **Fine [inferred].** These are descriptive metadata. |
| A non-affiliation line, e.g. "DevScene is an independent project, not affiliated with or endorsed by Anthropic. Claude and Claude Code are trademarks of Anthropic, PBC." | **Recommended [inferred].** It counters any implied endorsement. |

**Name check:** "DevScene", "DevScene Studio", "ragscene", "langscene", "tracescene" and "scenewise" contain no Anthropic mark. Issue #1's rule ("Claude Code" must not be part of the product's name) is met. A quick web search found no existing "DevScene" software trademark [15, secondary]. Nearby marks exist (DEVSCAPE, dead; DEVICESCAPE, live, Classes 9 and 42). A proper USPTO/EUIPO clearance search is outside Anthropic's terms and is an owner task before buying domains or registering a mark. **[ask]** a lawyer if a registration is planned.

### F6. Redistribution of Claude Code (Q5)

- Claude Code's `LICENSE.md`: *"© Anthropic PBC. All rights reserved. Use is subject to Anthropic's Commercial Terms of Service."* npm metadata: `license = 'SEE LICENSE IN README.md'`, latest `2.1.322` (2026-11-10) [9, verified]. It is proprietary and grants no right to redistribute.
- The two documents name different terms: `LICENSE.md` says Commercial Terms, while the legal page says Free/Pro/Max/Ultra users are under the Consumer Terms and Team/Enterprise/API users under the Commercial Terms [1]. The legal page's per-plan split is the more specific text and governs which terms a user is under. The redistribution conclusion ("All rights reserved", so no bundling) is the same either way.
- Legal page: *"preinstalling or running Claude Code in your products or services (e.g. in hosted sandboxes or other agent infrastructure) requires agreeing to our Commercial Terms of Service"* and *"The Claude Code binary must not be modified. Claude Code must be installed and run as published by Anthropic, and customers may not remove, disable, or restrict any authentication method built into it"* [1].
- Anthropic itself ships a Dev Container Feature (`ghcr.io/anthropics/devcontainer-features/claude-code`) and documents pinning with `npm install -g @anthropic-ai/claude-code@X.Y.Z` in a Dockerfile plus `DISABLE_AUTOUPDATER=1` [19, verified].

| Action | Verdict |
|---|---|
| Ship the `claude` binary or `@anthropic-ai/claude-code` inside the Studio bundle, the npm `devscene` package, or an AppImage/deb | **No [unambiguous]** |
| Publish a pre-built image to a registry with Claude Code inside (e.g. a "devscene-runner" image) | **No**, unless the owner accepts the Commercial Terms and meets the "customers offer Claude Code" conditions [1] **[strong reading]** |
| Ship a `devcontainer.json` or Dockerfile in a repo that installs Claude Code at build time on the user's machine | **Fine [strong reading].** It is the same pattern as Anthropic's own Dev Container Feature [19]; the user's build fetches the unmodified package from Anthropic's channel. |
| The user's own GitHub runner runs `npm install -g @anthropic-ai/claude-code` from a workflow template the user committed | **Fine [strong reading].** The user's own CI installs the unmodified package from Anthropic's channel, as `claude-code-action` does. The owner hosts and distributes nothing. |
| Studio detects that `claude` is missing and links to Anthropic's install page (https://code.claude.com/docs/en/setup) | **Fine.** Recommended. |
| Studio runs Anthropic's official installer command only after the user clicks "Install Claude Code", with the command shown | **Fine [strong reading].** The user installs from Anthropic's channel on their own machine; nothing is preinstalled "in your products". Link plus copy-button is still the nicer UX. |
| Studio requires a minimum `claude` version and tells the user to run `claude update` | **Fine** |

### F7. Monetisation (Q6)

| Model | Verdict |
|---|---|
| Donations (GitHub Sponsors, Open Collective, a Stripe payment link), as in item 18 and `funding.json` | **No Anthropic restriction found [strong reading].** Don't use Anthropic or Claude names or logos on the sponsor pages beyond plain-text description. |
| A paid tier of Studio (licence key, pro features), where users still bring their own Claude credential | **No Anthropic restriction found [strong reading].** The rule that matters is *"Customers may not pay for, resell, or intermediate Claude usage on their end users' behalf. Each end user must authenticate with their own Anthropic API key, Claude subscription plan credentials, or 3P inference provider credential"* [1]. A paid tier must not include Claude usage, credits or tokens. |
| A hosted "DevScene Cloud" that runs Claude Code on the owner's infrastructure | **Changes the picture.** It needs the Commercial Terms plus the two conditions (unmodified binary; each end user authenticates with their own credential and is billed directly) [1]. The Commercial Terms also bar reselling the Services *"except as expressly approved by Anthropic"* (D.4) [16]. **[ask]** before building it (email item f). |
| Does the owner need the Commercial Terms just to publish DevScene or Studio? | **No, as far as found [strong reading].** The tools make no API calls of their own and embed no Anthropic SDK. The Agent SDK is Commercial-Terms-governed [7], so adopting it later (instead of spawning the CLI) would bring Studio under the Commercial Terms and, by its auth note, onto API keys [7]. **Keep spawning the CLI.** |
| Do users need the Commercial Terms? | It depends on their plan, not on DevScene: API, Team and Enterprise users are under the Commercial Terms, and Free/Pro/Max/Ultra users are under the Consumer Terms [1]. See the EEA comparison below. |

**EEA vs US "non-commercial use" comparison:**
- **EEA/Swiss version** (served at [3] from every fetch location tried; contracting party Anthropic Ireland, Limited; effective 2025-10-08). In **§11 "Disclaimer of warranties, limitations of liability, and indemnity"**: *"**Non-commercial use only.** You agree that you will not use our Services for any commercial or business purposes and we and our Providers have no liability to you for any loss of profit, loss of business, business interruption, or loss of business opportunity."* The same terms *"apply to you if you are a consumer who is resident in the European Economic Area or Switzerland"*, and *"You are a consumer if you are acting wholly or mainly outside your trade, business, craft or profession"* [3, verified].
- **US / rest-of-world version** (Anthropic, PBC). Could not be fetched live: the page is geo-served, and the archived copies are EEA or older versions. Secondary sources say it has **no blanket clause**, only *"Use of our Services for evaluation purposes are for your personal, non-commercial use only"*: an HN thread quoting both texts (comments about 10 months old) [20] and a blog updated 2026-10-26 [21]. **[secondary]**
- **What it means (calmly):** the clause governs **which Anthropic plan an EEA/Swiss professional should use**, not whether DevScene may drive Claude. It reads mainly as a liability limit, and its own "consumer" definition makes it unclear whether a professional using Pro/Max for work is a "consumer" under these terms at all. It affects EEA users of DevScene on Pro/Max/Ultra doing paid work, and, if the owner is EEA-resident, the owner's own Pro/Max/Ultra use while building DevScene as a business. An API key (Commercial Terms) or Team/Enterprise avoids it entirely. Studio's docs should not market Pro/Max as the plan for business or team use. **[ask]** (email item e), and ask a lawyer if marketing to EEA professionals.

### F8. Studio's own open-source licence (Q7)

Apache-2.0, matching the harness, works with the 01 candidates:

| Framework (from 01) | Licence | Apache-2.0 Studio? | Extra obligations |
|---|---|---|---|
| Electron | MIT, plus bundled Chromium/FFmpeg and others | Yes | Ship Electron's `LICENSE` and `LICENSES.chromium.html` (electron-builder and Forge include them by default) [inferred] |
| Tauri 2 | MIT / Apache-2.0 | Yes | Rust crate notices (e.g. `cargo-about`); WebView2 is a Microsoft runtime, not redistributed by default |
| Flutter | BSD-3 | Yes | Flutter's `LICENSE` registry is shown by `showLicensePage` |
| Compose Multiplatform / Kotlin | Apache-2.0 | Yes | The bundled JRE (e.g. Temurin, GPLv2 + Classpath Exception) needs its licence shipped [inferred] |
| Wails, Fyne, Gio, iced, egui | MIT / Apache / BSD | Yes | Notices only |
| Avalonia | MIT | Yes | Notices only |
| Qt / PySide6 | LGPLv3 (Qt Essentials) | Yes, with dynamic linking | Re-linking, LGPL text, source offer (see 01). Some Qt add-on modules are GPLv3/commercial only, not LGPL: check each module's licence at qt.io before using add-ons [inferred] |
| PyQt6 | GPLv3 / commercial | **Only as GPLv3.** Studio's own source files can stay Apache-2.0 (Apache-2.0 code may be combined into a GPLv3 work), but the distributed combined app must be offered under GPLv3, or the owner buys a commercial PyQt licence (*"If your license is incompatible with the GPL then you need a commercial PyQt license"* [22]) | GPLv3 source obligations for the whole app |
| Slint | GPLv3 / Royalty-free 2.0 / commercial | Yes under Royalty-free (it requires Slint attribution in the app); own files can stay MIT or Apache-2.0 | — |

**Apache-2.0 duties (§4)** [17, verified]: give recipients a copy of the licence; carry prominent notices in modified files; keep copyright and attribution notices; and *"if the Work includes a 'NOTICE' text file … any Derivative Works that You distribute must include a readable copy of the attribution notices contained within such NOTICE file"*. Practical items:
- Add `LICENSE` and a `NOTICE` like the harness's to the Studio repo. Ship both inside every bundle (the About box, or `resources/`).
- If Studio copies harness code, it is the same author and licence; keep the harness's NOTICE line.
- Generate a third-party licences file at build time (`license-checker`/`license-report` for npm, `cargo-about` for Rust, Gradle licence plugins), and include fonts and icons.
- Apache-2.0 §6 grants **no trademark rights**, so "DevScene" stays the owner's. Consider a short trademark note in README so forks rename.
- Cross-reference 01: SignPath Foundation's free Windows signing requires that *"The project must use an OSI-approved Open Source license without commercial dual-licensing for all components"* and that *"The project may not contain any proprietary, non open-source component"* [23, verified; the page is marked draft]. So a later dual-licensed tier, **or proprietary pro features in the same project**, would lose eligibility.

## Compliance checklist — Studio (app-owned)

**Do**
- [ ] Spawn only the user's installed `claude` (via `devscene`/watcher scripts). Detect it with `claude --version` / `claude auth status`.
- [ ] If `claude` is missing or signed out, show instructions and links to Anthropic's install and login docs. Let the user act in their own terminal.
- [ ] Exclude `**/.credentials.json` under `~/.claude` **and under any `CLAUDE_CONFIG_DIR`** (macOS, Linux, Windows, and inside WSL) from every file watcher, log collector, crash reporter and diagnostics bundle.
- [ ] Before starting a **remote** run, check that the current `gh` user is allowed under the repo's credential policy (harness allow-list / `doctor --check-github`). Warn when the repo uses a personal `CLAUDE_CODE_OAUTH_TOKEN` and the user is not its owner.
- [ ] Recommend an API key, WIF, or Team/Enterprise for team repos, heavy unattended use, and EEA professional use.
- [ ] Describe Claude Code only in plain text ("runs your own Claude Code CLI"). Add a non-affiliation line on the website, the About box and the README.
- [ ] Ship LICENSE, NOTICE and a third-party licences file in every bundle.

**Don't**
- [ ] Don't use "Claude", "Claude Code" or "Anthropic" in the app name, feature names, menu labels styled as features, icons, logos or the domain.
- [ ] Don't use Anthropic or Claude logos, the sparkle mark, Claude Code's mascot or ASCII art, or a look-alike visual style.
- [ ] Don't offer Claude sign-in, embed Anthropic's OAuth page, or capture `claude setup-token` output.
- [ ] Don't read, copy, store, sync or transmit Claude credentials or tokens. Never pipe a token into `gh secret set`.
- [ ] Don't bundle, vendor, patch or proxy Claude Code. Don't set `ANTHROPIC_BASE_URL` or `ANTHROPIC_AUTH_TOKEN`.
- [ ] Don't sell, include or subsidise Claude usage in any paid tier, and don't pool accounts.
- [ ] Don't embed an interactive Claude chat or an alternative Claude Code front end (Issue #1 decision).
- [ ] Don't adopt the Agent SDK in the app without re-checking. It moves the app onto the Commercial Terms and API-key auth.

## Harness-owned action items (for `firu-daniel/devscene`, not Studio)

- **H1. Re-verify the citations in `docs/remote-execution.md` §9** (retrieved 2026-09-24, *"not re-fetched"*). The legal-page quotes still match on 2026-11-12. Three updates:
  - Line ~867: `CLAUDE_CODE_OAUTH_TOKEN` is documented on Pro, Max, **Ultra**, Team and Enterprise today [2, 4]; §9 omits Ultra.
  - "A paused billing change" paragraph: the help-centre page does not mention GitHub Actions, so drop "and GitHub Actions" from the description of the paused change, and add the **2026-10-07** notice (monthly API credits on Max/Ultra/Team for API-key usage from a linked Console org; plan sign-in unchanged) [8].
  - The "$20 / $100 / $200" figures are not on today's page; re-source them as "announced 2026-05-13, then paused" [12, secondary] rather than citing [8] for them.
- **H2. Keep the claude-installing workflow steps as they are:** install from Anthropic's npm package on the user's runner, never from a harness-hosted mirror, cache or container image. Consider pinning to a version the harness tested (the comments mention `2.1.284`) with `npm install -g @anthropic-ai/claude-code@X.Y.Z` and `DISABLE_AUTOUPDATER=1`, the pattern Anthropic documents [19]. That is a reliability choice, not a terms one.
- **H3. Never publish a pre-built "devscene runner" image with Claude Code inside** unless the owner first accepts the Commercial Terms and meets the conditions in [1]. A `devcontainer.json` or Dockerfile that installs Claude Code at build time on the user's machine is fine (F6).
- **H4. Keep the token flow manual** (`claude setup-token`, then `gh secret set` typed by the user). Never automate it inside `devscene init` or `doctor`.
- **H5. Team credential guard.** Keep and surface `doctor --check-github`'s warnings (a personal OAuth token while the trigger list is `*`, or while writers are beyond the list). The guard is partial: a list naming several teammates while the owner's `CLAUDE_CODE_OAUTH_TOKEN` is set gets only a note (`checks.ts` ~3224–3250). Add a **warning** when an OAuth token is set and `DEVSCENE_RUN_ACTORS` names more than one login, and consider making `init` default to refusing `*` when `CLAUDE_CODE_OAUTH_TOKEN` is set. This follows Consumer Terms §2 and the "tied to the subscription of the person who ran `claude setup-token`" guidance [3, 4] (graded [strong reading], F4).
- **H6. Security hygiene (not a terms issue).** `settings.autonomous.json`'s `sandbox.credentials.files` denies `~/.ssh`, `~/.config/gh` and others, but not `.credentials.json`. That is where the user's Claude login lives on Linux and WSL (and on macOS when the Keychain write fails), under `~/.claude` or under `CLAUDE_CONFIG_DIR` if set [2]. Measure whether denying it to sandboxed commands and the `Read` tool breaks the CLI's own auth (it should not: the CLI reads it outside the sandbox), then add it, covering any configured config directory.
- **H7. Branding.** "An autonomous SDLC harness for Claude Code" in plugin.json, marketplace.json, the README and the npm description is descriptive and acceptable [strong reading]. Add the non-affiliation sentence to the README (not NOTICE; NOTICE is for Apache attribution). Avoid "Powered by Claude" badges. The plugin and command namespace `devscene:` is fine.
- **H8. Never use `--bare`** for subscription-authenticated runs (it does not read `CLAUDE_CODE_OAUTH_TOKEN` [2]). `remote-run.sh` already notes this.
- **H9. If the plugin is ever listed in an Anthropic directory or marketplace**, the Usage Policy adds: *"Software listed in our Directories must comply with our Software Directory Policy"* [6]. Read that policy before submitting.

## Answers to the owner's questions

1. **Subscription in an automated tool.** A subscriber running the stock `claude -p` with their own Pro/Max/Ultra login, locally or with their own `setup-token` token in their own CI, is explicitly documented and permitted [2, 3, 8, 10]. **[unambiguous]** DevScene or Studio spawning that unmodified binary is within the "unmodified binary" carve-out [1]. **[strong reading]**, with one narrow **[ask]** (email item a) whose worst case is steering users to API keys. What is prohibited is a product that offers Claude login, harvests or relays tokens, or routes, resells or pays for usage [1, 6]. **[unambiguous]** Heavy unattended use sits under "ordinary, individual usage" limits and possible enforcement without notice. **[ask]**
2. **Studio by spawning only.** Yes, if it follows the "never" list in F3: no credential file reads, no sign-in UI, no token capture, no bundling or patching or proxying, no chat. **[strong reading]**
3. **GitHub Actions.** `ANTHROPIC_API_KEY`, `CLAUDE_CODE_OAUTH_TOKEN` (Pro, Max, Ultra, Team, Enterprise), WIF, and Bedrock/Vertex/Foundry are all documented [4]. A subscription token is permitted for the subscriber's own runs [unambiguous]. Runs other people trigger on it most plausibly are not, though Anthropic's own action lets any writer trigger runs on an installed token [3, 4]. **[strong reading]**, confirm in the email (item d); meanwhile use an API key, WIF or Team/Enterprise for team repos.
4. **Naming.** Not in the name or logo, and no logos without permission. **[unambiguous]** Plain-text "runs/works with Claude Code" in body text is allowed by the legal page's wording and is ordinary descriptive use. **[strong reading]**, confirm in the email (item c). The Agent SDK forbids "Claude Code" naming and look-alikes. All six names are clean.
5. **Redistribution.** Claude Code is proprietary ("All rights reserved"). Studio and the harness must not bundle it or publish a pre-built image with it. **[unambiguous]** The workflow's install-on-runner step and a build-time devcontainer install are fine. **[strong reading]**
6. **Monetisation.** Donations and a paid app tier are fine if users bring their own Claude credential and no Claude usage is sold. **[strong reading]** Hosted runs would need the Commercial Terms. **[ask]** Users' plan type decides their own terms; EEA/Swiss Pro/Max/Ultra users doing paid work (possibly the owner) should use an API key or Team plan or get confirmation (F7). **[ask]**
7. **Apache-2.0.** It is compatible with every permissive candidate in 01, and with Qt/PySide6 under LGPL dynamic linking (check add-on modules). With PyQt6 the shipped app must be GPLv3 or the owner buys a commercial PyQt licence. Ship LICENSE, NOTICE and third-party notices. **[unambiguous]**
8. **Not legal advice.** The grading is inline above. All **[ask]** items go to Anthropic in one email (below). Ask a lawyer: the trademark clearance of "DevScene", and the EEA consumer "non-commercial" clause if marketing to professionals.

## Draft email to Anthropic

Send through the "contact sales" link on the legal page, as it directs for authentication questions [1]. Copy the naming item (c) to marketing@anthropic.com, which §13 names for brand permissions [3]. Fill in the bracketed parts.

> **Subject:** Permitted authentication for an open-source tool that launches the user's own Claude Code CLI
>
> Hello,
>
> I maintain DevScene (https://github.com/firu-daniel/devscene, Apache-2.0), an open-source workflow harness, and I am building DevScene Studio, a free desktop app that manages its runs. Neither product calls the Anthropic API, embeds an Anthropic SDK or handles credentials. They launch the user's own installed, unmodified `claude` binary in headless mode (`claude -p … --output-format stream-json`), locally or in the user's own GitHub Actions runner, and that binary authenticates however the user set it up: a Claude plan login, a `claude setup-token` token, an API key, or a cloud provider. The tools never read, store or relay tokens, never offer a Claude sign-in, and do not bundle Claude Code; users install it from your channels.
>
> Your legal and compliance page invites questions about authentication for a use case, so I would be grateful for written confirmation on these points:
>
> (a) **"Products or services that interact with Claude's capabilities."** Is a tool like this, which only launches the user's own unmodified `claude -p`, ordinary use of Claude Code by that user, or is it one of the "products or services that interact with Claude's capabilities" that should use API key authentication? If the latter, is it enough for our docs to recommend API keys while still allowing users to run their own plan login?
>
> (b) **Sustained unattended use.** Are long-running, unattended `claude -p` sessions (several in parallel) on a user's personal Max or Ultra plan, on their own machine or in their own GitHub Actions, acceptable within the published plan limits?
>
> (c) **Descriptive wording.** May we say, in plain body text on the website and README, that DevScene "works with Claude Code" or "runs your own Claude Code CLI", with a non-affiliation notice and no Anthropic logos? We will not use Claude or Anthropic in any product or feature name. Is a "Powered by Claude" tagline acceptable for a tool that does not use the Agent SDK?
>
> (d) **Teammates and one subscription token.** In a repository whose `CLAUDE_CODE_OAUTH_TOKEN` secret holds the owner's subscription token, may collaborators with write access trigger CI runs that use it (as `claude-code-action` allows), or must such repositories use an API key, workload identity federation or Team/Enterprise seats?
>
> (e) **EEA non-commercial use.** The Consumer Terms served to EEA/Swiss residents (Anthropic Ireland, Limited, §11) say Pro/Max/Ultra may not be used "for any commercial or business purposes". Does this apply to a professional developer [in [country]] using a Pro/Max/Ultra plan with Claude Code for paid or business work, including building this open-source tool? If so, is an API key or a Team plan the right choice?
>
> (f) **Later, not now.** If we ever offered hosted runs on our own infrastructure, with each user authenticating with their own credential and billed directly by Anthropic, is accepting the Commercial Terms and meeting the "Can customers offer Claude Code in their products?" conditions sufficient, or is a separate agreement needed?
>
> Thank you,
> [Name]
> [Role, country of residence]

## Risks and open questions

- **Policy volatility (high).** The terms changed at least four times in 2026: January, February, April and the paused June change; the Usage Policy itself took effect on 2026-11-12, the day of this check [6]. Enforcement can come *"without prior notice"* [1]. Mitigation: keep the API-key path first-class in docs and the UI, and re-run this check every quarter and before any paid tier.
- **The "should use API key" sentence for developer products** is the one textual question about the subscription path. **[ask]** (email item a). Worst case: credential-type guidance changes; the harness keeps working.
- **Team use of one person's token.** This is the most likely real-world problem, graded [strong reading] (F4). Studio's "teammate whose repo someone else set up" persona makes it more likely. Guard it (F4, H5) and ask (email item d).
- **EEA "non-commercial use only".** The EEA/Swiss Consumer Terms (§11) bar commercial or business use of consumer plans [3, verified]; the US text reportedly does not [20, 21, secondary]. This decides plan choice for EEA professionals, possibly the owner, not whether the harness may use Claude. **[ask]** (email item e) and a lawyer if marketing to EEA professionals.
- **Hosted or cloud features** later (cloud runners, a shared run service) would move the owner onto the Commercial Terms. Re-check before designing them (email item f).

## Sources

All accessed 2026-11-12.

1. https://code.claude.com/docs/en/legal-and-compliance — License (Consumer vs Commercial Terms), "Can customers offer Claude Code in their products?", name and logo use, "Usage policy › Acceptable use" ("ordinary, individual usage"), "Authentication and credential use", unmodified-binary carve-out, API keys for "the customer's own authorized users", contact sales; no longer contains the February "in any other product, tool, or service" wording [verified]
2. https://code.claude.com/docs/en/authentication — `claude setup-token`, `CLAUDE_CODE_OAUTH_TOKEN`, plan requirements, precedence, credential storage paths, `CLAUDE_CONFIG_DIR` relocation of `.credentials.json` and the Keychain entry, bare mode [verified]
3. https://www.anthropic.com/legal/consumer-terms — effective 2025-10-08 (served as Anthropic Ireland, Limited); §2 credential sharing, §3 automated access and competing products, §11 "Non-commercial use only" and the EEA/Swiss consumer definition, §13 "Use of our brand" [verified, exact text extracted from page HTML]
4. https://code.claude.com/docs/en/github-actions — CI secrets, OAuth token plans, quick setup minting a subscription token, "Who can trigger runs" (write access), org-level guidance to use an API key, WIF, cost note [verified]
5. https://www.anthropic.com/legal/trademark-guidelines — effective 2024-08-01; permission, endorsement, logo alteration, ™ symbol rules [verified]
6. https://www.anthropic.com/legal/aup — Usage Policy effective 2026-11-12; resell/proxy/route-through-consumer-subscriptions, multiple accounts, agentic use, Software Directory Policy [verified, exact text extracted from page HTML]
7. https://code.claude.com/docs/en/agent-sdk/overview — CLI-as-subprocess equivalence, Agent SDK branding guidelines, "claude.ai login or rate limits" note, Commercial Terms governance [verified]
8. https://support.claude.com/en/articles/15036540 — "Use the Claude Agent SDK with your Claude plan"; 2026-06-15 pause (incl. "third-party app usage still draw from your subscription limits"), 2026-10-07 monthly API credits; no dollar amounts, no mention of GitHub Actions [verified; page gives no exact update date]
9. https://github.com/anthropics/claude-code/blob/main/LICENSE.md (via `gh api`) and `npm view @anthropic-ai/claude-code` — "All rights reserved"; v2.1.322, modified 2026-11-10 [verified]
10. https://code.claude.com/docs/en/cli-reference — `claude auth login|logout|status`, `claude setup-token`, `claude -p` [verified]
11. https://www.theregister.com/2026/02/20/anthropic_clarifies_ban_third_party_claude_access — February 2026 clarification (now superseded), OpenCode commit citing "anthropic legal requests"; does not name RooCode or confirm Cline/OpenClaw as broken [secondary]
12. https://falcao.org/posts/anthropic-claude-access-crackdown-ecosystem-fallout/ (2026-01-09 block naming OpenCode, Cline, RooCode, OpenClaw; 2026-03-19 legal demands to OpenCode; 2026-04-04 change; 2026-05-13 credit announcement with $20/$100/$200 figures), https://lilting.ch/en/articles/anthropic-claude-code-openclaw-third-party-paygo (April 2026 billing change) [secondary]. https://thenewstack.io/anthropic-claude-harness-restrictions/ returned 403 on 2026-11-12 and is unavailable.
13. https://github.com/anthropics/claude-code/issues/24600 (via `gh`) — "Branding guidelines should address third-party projects that wrap Claude Code CLI", closed not-planned by the inactivity bot 2026-03-11, no Anthropic answer [verified]
14. https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan — now titled "Use Claude Code with your Pro, Max, or Ultra plan"; five-hour and weekly limits, verified Ultra has no five-hour limit; no CI/script restriction stated [verified]
15. Web search "DevScene" software or trademark (trademarkdir.com, markinton.com results) — no DevScene mark found; nearby marks DEVSCAPE, DEVICESCAPE [secondary, not a clearance search]
16. https://www.anthropic.com/legal/commercial-terms — effective 2025-06-17; scope (API keys, not for consumer use), D.4 use restrictions including resale [verified]
17. https://www.apache.org/licenses/LICENSE-2.0 — §4 redistribution and NOTICE, §6 trademarks [verified from the harness's LICENSE copy]
18. Harness repo `/Users/daniel/Work/devscene`: `README.md`, `NOTICE`, `LICENSE`, `funding.json`, `cli/templates/github/workflows/devscene-{run,control}.yml`, `cli/templates/scripts/autonomous-watcher.sh`, `cli/templates/claude/settings.autonomous.json`, `cli/src/doctor/checks.ts`, `docs/remote-execution.md` — read 2026-11-12
19. https://code.claude.com/docs/en/devcontainer — official Dev Container Feature `ghcr.io/anthropics/devcontainer-features/claude-code`, pinned `npm install -g @anthropic-ai/claude-code@X.Y.Z`, `DISABLE_AUTOUPDATER` [verified]
20. https://news.ycombinator.com/item?id=46595957 — comments quoting the non-EEA "evaluation purposes … personal, non-commercial use only" sentence and the EEA "Non-commercial use only" clause [secondary; comments about 10 months old]
21. https://autonomee.ai/blog/claude-code-terms-of-service-explained/ — updated 2026-10-26; says only the EEA/Swiss version carries the blanket non-commercial clause [secondary]
22. https://www.riverbankcomputing.com/commercial/license-faq — "If your license is incompatible with the GPL then you need a commercial PyQt license" [verified]
23. https://signpath.org/terms — OSS licence "without commercial dual-licensing for all components"; no "proprietary, non open-source component"; page marked draft [verified]
24. https://claude.com/pricing — Ultra plan ($200/month) includes Claude Code [verified by reviewer, 2026-11-12]
