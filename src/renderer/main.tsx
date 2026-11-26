import { StrictMode, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import type { StudioApi } from "../shared/contract/studio-api";
import { App } from "./App";
import { createIpcStudio } from "./studio/ipc";
import { installStudio } from "./studio/studio";
import { StartupError } from "./ui/StartupError";
import "./styles.css";

// Composition root: picks the StudioApi adapter by build mode, never by whether
// `window.studio` exists (07 §2 row 14). Vite replaces `import.meta.env.MODE` statically,
// and the dynamic import keeps the fixture code out of the Electron build.
async function createStudio(): Promise<StudioApi> {
  if (import.meta.env.MODE === "browser") {
    const { createFixtureStudio } = await import("./studio/fixture");
    return createFixtureStudio(window.location.search);
  }
  return createIpcStudio();
}

const container = document.getElementById("root");
if (!container) throw new Error("#root is missing from index.html");
const root = createRoot(container);
const render = (node: ReactNode) =>
  root.render(<StrictMode>{node}</StrictMode>);

try {
  installStudio(await createStudio());
  render(<App />);
} catch (error) {
  render(
    <StartupError
      message={error instanceof Error ? error.message : String(error)}
    />,
  );
}
