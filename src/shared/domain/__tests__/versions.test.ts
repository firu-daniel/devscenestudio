import { describe, expect, it } from "vitest";
import { describeVersions } from "../versions";

describe("describeVersions", () => {
  it("lists the three runtimes in a fixed order", () => {
    expect(
      describeVersions({
        electron: "45.5.0",
        chrome: "156.0.0.0",
        node: "24.22.3",
      }),
    ).toBe("Electron 45.5.0 · Chromium 156.0.0.0 · Node 24.22.3");
  });
});
