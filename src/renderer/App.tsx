import { describeVersions } from "../shared/domain/versions";
import { getStudio } from "./studio/studio";

export function App() {
  return (
    <main className="grid min-h-screen place-items-center">
      <div className="text-center">
        <h1 className="text-3xl font-semibold">DevScene Studio</h1>
        <p className="opacity-70" data-testid="versions">
          {describeVersions(getStudio().versions)}
        </p>
      </div>
    </main>
  );
}
