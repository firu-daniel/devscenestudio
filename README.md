# DevScene Studio

Desktop app for [DevScene](https://github.com/firu-daniel/devscene) runs. Early skeleton: the Electron validation spike is tracked in [#4](https://github.com/firu-daniel/devscenestudio/issues/4). The research behind it is in [`docs/product-startup-research/`](docs/product-startup-research/README.md).

## Development

Requires Node.js 22.12 or later.

```sh
npm install
npm start          # compile and launch
npm run typecheck
```

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

Create the keychain profile with `xcrun notarytool store-credentials <profile> --key <AuthKey.p8> --key-id <id> --issuer <issuer>`, using an App Store Connect API key with the Developer role. Checks after a build are in [research 11 §2](docs/product-startup-research/11-day0-signing.md#2-macos-checks-pass-conditions).

## Licence

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
