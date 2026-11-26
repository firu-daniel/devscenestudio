import type { StudioApi } from "../../shared/contract/studio-api";

// The renderer's only way to reach the outside world (07 §2 row 20). A module-level
// singleton rather than a React context, so code outside React (stores, query functions)
// can reach it too. main.tsx installs the adapter once, before the first render; tests
// install a fake.
let installed: StudioApi | undefined;

export function installStudio(api: StudioApi): void {
  installed = api;
}

export function getStudio(): StudioApi {
  if (!installed) {
    throw new Error(
      "StudioApi is not installed: main.tsx installs it before rendering.",
    );
  }
  return installed;
}
