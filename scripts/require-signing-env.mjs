// Refuses a release build that would come out unsigned or un-notarized.
// The identity and credentials live outside the repo (see README, "Signed macOS builds").
const required = ["CSC_NAME", "APPLE_KEYCHAIN_PROFILE"];
const missing = required.filter((name) => !process.env[name]);

if (missing.length > 0) {
  console.error(`Release build refused: ${missing.join(", ")} not set.`);
  console.error("Source your private signing env file first, e.g. `source ~/.config/devscenestudio/signing.env`.");
  process.exit(1);
}
