import { describeVersions } from "../shared/domain/versions";
import type { StudioApi } from "../shared/contract/studio-api";

export function App({ studio }: { studio: StudioApi | undefined }) {
  return (
    <main className="grid min-h-screen place-items-center">
      <div className="text-center">
        <h1 className="text-3xl font-semibold">DevScene Studio</h1>
        <p className="opacity-70" data-testid="versions">
          {studio ? describeVersions(studio.versions) : "Browser mode"}
        </p>
      </div>
    </main>
  );
}
