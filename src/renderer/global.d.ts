import type { StudioApi } from "../shared/contract/studio-api";

declare global {
  interface Window {
    // Set by the preload in Electron; absent in a plain browser. Read only by studio/ipc.ts.
    readonly studio?: StudioApi;
  }
}
