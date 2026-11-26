import type { StudioApi } from "../../shared/contract/studio-api";
import { DEFAULT_SCENARIO, scenarios } from "./fixtures";

// The browser-mode adapter: an in-memory StudioApi playing one scenario. main.tsx loads
// this module with a dynamic import only when MODE === "browser", so the Electron build
// carries no fixture code. The scenario comes from the URL, not storage: the harness QA
// agent clears storage between cases (06 §6).
export function createFixtureStudio(search: string): StudioApi {
  const name = new URLSearchParams(search).get("scenario") ?? DEFAULT_SCENARIO;
  if (!Object.hasOwn(scenarios, name)) {
    const known = Object.keys(scenarios).join(", ");
    throw new Error(`Unknown scenario "${name}". Known scenarios: ${known}.`);
  }
  const scenario = scenarios[name]!;
  return { versions: Object.freeze({ ...scenario.versions }) };
}
