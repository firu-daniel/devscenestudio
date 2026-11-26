import type { RuntimeVersions } from "../domain/versions";

// What the preload exposes on `window.studio`. Implemented by src/preload/preload.ts.
export interface StudioApi {
  readonly versions: RuntimeVersions;
}
