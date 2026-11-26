import type { StudioApi } from "../shared/contract/studio-api";

declare global {
  interface Window {
    // Set by the preload in Electron. Absent in a plain browser.
    readonly studio?: StudioApi;
  }
}
