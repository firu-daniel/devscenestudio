// Shown when the StudioApi adapter can't be created: a failed preload in Electron, or an
// unknown `?scenario=` in browser mode.
export function StartupError({ message }: { message: string }) {
  return (
    <main className="grid min-h-screen place-items-center p-8">
      <div className="max-w-xl text-center" role="alert">
        <h1 className="text-2xl font-semibold">
          DevScene Studio could not start
        </h1>
        <p className="mt-2 opacity-70" data-testid="startup-error">
          {message}
        </p>
      </div>
    </main>
  );
}
