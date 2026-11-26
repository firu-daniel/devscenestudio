import type { RuntimeVersions } from "../domain/versions";

// The renderer's port to the outside world, reached only through getStudio(). Implemented by
// the preload (`window.studio`, src/preload/preload.ts) and by the browser-mode fixture
// (src/renderer/studio/fixture.ts).
export interface StudioApi {
  readonly versions: RuntimeVersions;
}
