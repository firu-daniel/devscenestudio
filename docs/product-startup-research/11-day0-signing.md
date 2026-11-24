# 11 — Day 0 of the spike: macOS notarization and Windows signing

> Status: draft (not yet reviewed) · Date: 2026-11-24 · Area owner: owner session · Expands: [`10-recommendation.md`](10-recommendation.md) §5, row "Day 0"
>
> Confidence tags as in the other files: **[verified]** (primary source checked on 2026-11-24), **[secondary]**, **[inferred]**.

## TL;DR

- **Goal.** Prove early, in about half a day, that a signed and notarized Electron build passes Gatekeeper on a downloaded copy. 2026 forum reports describe new Apple teams stuck at notarization `statusCode 7000` for weeks to months (04 §6), and Day 0 finds this out while the rest of the spike goes on.
- **Account (D4).** Pre-release builds are signed with an existing organisation account the owner holds, on the owner's Mac only, never in this repo's CI. The check is **repeated with the publishing identity** (a personal individual account) a few weeks before the first public release, because a new team can hit the `7000` stall again.
- **Windows (D3) is not a Day 0 step.** The SignPath Foundation signs only projects that are **already released** and have **verifiable reputation**. The first Windows release therefore ships unsigned, with SmartScreen warnings, and the application follows it (§3). **[verified]** This corrects 10 §5, which put the Windows signing route on Day 0.

## 1. macOS: steps

electron-builder's current stable docs are v26; the v27 docs (unreleased, "next") change a few keys, noted where they differ [1][2].

1. **Developer ID Application certificate.** Create it in the developer account or Xcode. The required role is **Account Holder**, and an account can hold up to five Developer ID Application certificates [3]. **[verified]** Keep the certificate and its private key in the owner's login keychain. Don't export it to CI or into this repo.
2. **Notarization credentials.** Either of these [1][2]: **[verified]**
   - **App Store Connect API key** (preferred: revocable, no Apple ID password): `APPLE_API_KEY` (base64 of the `.p8`; v27 also accepts a path), `APPLE_API_KEY_ID`, `APPLE_API_ISSUER`. v26 lists `APPLE_TEAM_ID` beside them; v27 says it isn't used with an API key.
   - **Apple ID + app-specific password:** `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD` (created at appleid.apple.com, never the Apple ID password itself), `APPLE_TEAM_ID`.
   - Or a stored keychain profile: `APPLE_KEYCHAIN_PROFILE` (optional `APPLE_KEYCHAIN`).

   Keep these values in the shell session or keychain, not in a committed `.env`.
3. **Hello-world Electron app with electron-builder:**
   - `mac.notarize: true`, which makes the credentials mandatory. In v27, notarization runs whenever credentials are set, and `true` makes them required [1].
   - `hardenedRuntime: true`. Notarization requires it. v26 sets it on `mac`; v27 moves it to `mac.sign`. Neither page says it is on by default, so set it explicitly [1][2]. **[verified]**
   - **No App Sandbox.** Studio must spawn `git`, `gh` and `devscene` on arbitrary repos (04 §6).
   - **Entitlements:** Electron needs `com.apple.security.cs.allow-jit`. The two doc versions disagree on the rest:
     - v26 lists `allow-jit` and `allow-unsigned-executable-memory` as the minimum [2];
     - v27 grants `allow-jit` by default and warns: "Do **not** add `com.apple.security.cs.allow-unsigned-executable-memory` out of habit" [1].

     **[verified]** Start with `allow-jit` alone. Add the second one only if the signed app crashes at launch, and record which electron-builder version needed it.
   - **Signing identity:** with no identity set, electron-builder looks for a valid certificate in the keychain, and **skips signing if it finds none** [4]. Pin the identity (`mac.identity` in v26, `mac.sign.identity` in v27), so a missing certificate fails the build instead of silently producing an unsigned app. **[verified]** / [inferred for the pinning advice]
4. **Build.** electron-builder signs, submits for notarization, waits, and staples automatically when it notarizes [1][2]. **[verified]**

## 2. macOS: checks (pass conditions)

| Check | Command or action | Pass |
|---|---|---|
| Notarization accepted | electron-builder's notarize step | Accepted. **No `statusCode 7000`** ("Team is not yet configured for notarization"), which only Apple Developer Program Support can clear (04 §6) |
| Signature | `codesign --verify --deep --strict --verbose=2 <App>.app` | No errors [2] |
| Gatekeeper | `spctl --assess --verbose --type exec <App>.app` | `accepted` with `source=Notarized Developer ID` [1][2] **[verified]** (electron-builder's docs, not Apple's) |
| Staple | `xcrun stapler validate <App>.app` | "The validate action worked!" [1][2] |
| Downloaded copy | Zip the app, fetch it through a browser (so macOS sets the quarantine flag), open it, ideally on a second Mac or user account | Opens with no "Open Anyway" trip to System Settings. Since macOS 15 that trip is the only bypass for unsigned apps (04 §6) |
| Hardened Runtime and spawning (optional) | From the app, spawn `/opt/homebrew/bin/gh --version` and `git --version` | Both run. 04 §6 says Hardened Runtime doesn't block separately signed binaries **[verified in 04]** |
| Timing (record) | Wall-clock time from submit to accepted | Logged for the release checklist |

On a rejection, read the notarization log for the submission ID. `xcrun notarytool log <id>` is the usual route **[inferred]**: Apple's notarization workflow page didn't render when fetched, so the exact command is unverified here [5].

## 3. Windows: SignPath Foundation, after the first release

SignPath Foundation conditions, read 2026-11-24 [6]: **[verified]**
- **Licence:** "an OSI-approved Open Source license without commercial dual-licensing for all components", and "no proprietary, non open-source component". Met by D2, Apache-2.0.
- **Maturity:** "The project must already be released in the form that should be signed." It must be actively maintained, its functionality described on its download page, and "we require a certain verifiable reputation". No threshold is stated, and acceptance is at their discretion ("under no obligation to accept your project").
- **Team:** MFA on SignPath and on GitHub for every member. A team member reviews changes from non-committers, and an approver manually approves each signing request. The signing team must own the repository. A one-person team fits **[inferred]**.
- **Builds:** "a valid, automated build resulting from the source code" at the repository, where build scripts and CI configuration count as source. Product name and version attributes must be set and consistent. No CI system is named on the pages read; GitHub is named only as an example.
- **Publisher:** the certificate is issued to SignPath Foundation, so Windows shows **SignPath Foundation as the publisher**, with the project name as the product name.
- **Policy page:** the project must publish a "Code signing policy" with the line "Free code signing provided by SignPath.io, certificate by SignPath Foundation".
- **Applying:** through https://signpath.org/apply. No processing time is stated. The code-of-conduct section of the terms page is marked draft.

**What this means for Studio [inferred]:**
- The first Windows release, or a public pre-release, ships **unsigned**. Users see SmartScreen's "Windows protected your PC" and click through More info → Run anyway.
- Apply once there is a release, a download page describing the app, and an automated CI build of the Windows artifact.
- The CI build must be reproducible from the public repo. That fits the planned release workflow (10 §6 item 9).
- If waiting is unacceptable, the paid routes in 10 §4 (D3) still apply: Artifact Signing ≈ US$120/yr if eligible, or an OV certificate.

## Risks and open questions

- The `7000` stall reports are anecdotal (04 §6). The organisation account used for pre-release builds is already set up, so it will probably notarize fine. That doesn't predict how the new personal account will behave.
- electron-builder v27 changes several keys (`mac.sign.*`, entitlements defaults, `APPLE_TEAM_ID`). Pin the electron-builder version in the spike and re-read the docs on upgrade.
- Builds signed by the interim account won't auto-update to builds signed by the publishing identity. Testers reinstall once (10 §4.0, D4).
- SignPath's reputation bar is unstated, so the time from first release to signed Windows builds is unknown.
- https://about.signpath.io/product/open-source failed to load when fetched, so any extra conditions it lists are unread.

## Sources

1. https://www.electron.build/docs/notarization — electron-builder notarization, v27 ("next") docs: credentials, `mac.sign`, default `allow-jit`, automatic stapling, verification commands. Accessed 2026-11-24.
2. https://www.electron.build/v26/docs/notarization — the same page for stable v26: `hardenedRuntime: true`, the entitlements minimum, `APPLE_TEAM_ID` with an API key. Accessed 2026-11-24.
3. https://developer.apple.com/help/account/create-certificates/create-developer-id-certificates/ — Developer ID certificates: Account Holder role, up to five per type. Accessed 2026-11-24.
4. https://www.electron.build/docs/features/code-signing/code-signing-mac — keychain identity search; signing skipped if none is found; `identity: "-"` and `null`. Accessed 2026-11-24.
5. https://developer.apple.com/documentation/security/customizing-the-notarization-workflow — fetched 2026-11-24; only the title rendered, so nothing is cited from it.
6. https://signpath.org/terms , https://signpath.org/ , https://signpath.org/apply — SignPath Foundation conditions for open-source projects. Accessed 2026-11-24.
