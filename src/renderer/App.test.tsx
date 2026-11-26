import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "./App";

describe("App", () => {
  it("shows the runtime versions the preload exposes", () => {
    render(
      <App
        studio={{
          versions: {
            electron: "45.5.0",
            chrome: "156.0.0.0",
            node: "24.22.3",
          },
        }}
      />,
    );
    expect(screen.getByTestId("versions")).toHaveTextContent(
      "Electron 45.5.0 · Chromium 156.0.0.0 · Node 24.22.3",
    );
  });

  it("says browser mode when there is no preload", () => {
    render(<App studio={undefined} />);
    expect(screen.getByTestId("versions")).toHaveTextContent("Browser mode");
  });
});
