# DevScene Studio

Desktop app for [DevScene](https://github.com/firu-daniel/devscene) runs. Early skeleton: the Electron validation spike is tracked in [#4](https://github.com/firu-daniel/devscenestudio/issues/4). The research behind it is in [`research/product-startup-research/`](research/product-startup-research/README.md).

## Development

Requires Node.js `^22.22.2` or `^24.15.0`. Install scripts are off (`.npmrc`).

```sh
npm install
npm start             # build and launch the Electron app
npm run dev:browser   # the renderer alone, in a browser (Vite dev server)
npm run check         # tsc -b (per-process projects) + ESLint
npm test              # Vitest: `node` and `dom` (jsdom) projects
npm run format        # Prettier check (`npm run format:write` to fix)
```

Layout: `src/shared` (pure TypeScript), `src/main`, `src/preload` and `src/renderer` (one folder per Electron process), and `tests/` for cross-layer suites. Each has its own `tsconfig.json`, so an import from one process into another fails the type check. Vite builds the renderer and esbuild bundles main and preload (`scripts/build-main.mjs`). The architecture is in [`research/architecture-research/07-recommendation.md`](research/architecture-research/07-recommendation.md).

## Signed macOS builds

Release builds are signed with a Developer ID Application certificate and notarized. The signing identity and the notarization credentials stay **outside this repository**: put them in a private env file and source it before building.

```sh
# ~/.config/devscenestudio/signing.env (chmod 600, never committed)
export CSC_NAME="<certificate name without the 'Developer ID Application: ' prefix>"
export APPLE_KEYCHAIN_PROFILE="<notarytool keychain profile>"
```

```sh
source ~/.config/devscenestudio/signing.env
npm run dist:mac   # refuses to run when either variable is unset
```

Create the keychain profile with `xcrun notarytool store-credentials <profile> --key <AuthKey.p8> --key-id <id> --issuer <issuer>`, using an App Store Connect API key with the Developer role. Checks after a build are in [research 11 §2](research/product-startup-research/11-day0-signing.md#2-macos-checks-pass-conditions).

## Licence

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
