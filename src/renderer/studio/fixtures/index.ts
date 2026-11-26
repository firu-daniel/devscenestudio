import type { StudioApi } from "../../../shared/contract/studio-api";

// Browser-mode scenarios, selected with `?scenario=<name>`. Typed against the contract, so
// a contract change breaks them at `tsc -b`. Timed live events and the 300-card board
// arrive with #12.
export interface Scenario {
  readonly versions: StudioApi["versions"];
}

export const DEFAULT_SCENARIO = "default";

export const scenarios: Readonly<Record<string, Scenario>> = {
  [DEFAULT_SCENARIO]: {
    versions: { electron: "fixture", chrome: "fixture", node: "fixture" },
  },
};
