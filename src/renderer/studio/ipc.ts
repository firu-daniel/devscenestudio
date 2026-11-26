import type { StudioApi } from "../../shared/contract/studio-api";

// The Electron adapter: the preload's `window.studio`. A missing preload means it failed
// to load, so fail loudly. Never fall back to fixtures (01 §5).
export function createIpcStudio(): StudioApi {
  const studio = window.studio;
  if (!studio) throw new Error("Preload failed: window.studio is missing.");
  return studio;
}
