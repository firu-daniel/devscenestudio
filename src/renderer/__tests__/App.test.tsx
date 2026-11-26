import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "../App";
import { installStudio } from "../studio/studio";

describe("App", () => {
  it("shows the runtime versions from the installed StudioApi", () => {
    installStudio({
      versions: { electron: "45.5.0", chrome: "156.0.0.0", node: "24.22.3" },
    });
    render(<App />);
    expect(screen.getByTestId("versions")).toHaveTextContent(
      "Electron 45.5.0 · Chromium 156.0.0.0 · Node 24.22.3",
    );
  });
});
