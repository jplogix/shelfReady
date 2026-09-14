export function ErrorState({
  title = "We could not load this page",
  message,
  onRetry,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="rounded border border-red/30 bg-red-soft px-4 py-4 text-sm text-red" role="alert">
      <p className="font-medium">{title}</p>
      <p className="mt-1">{message}</p>
      {onRetry && (
        <button type="button" className="mt-3 min-h-11 underline" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded border border-dashed border-line px-4 py-10 text-center text-ink-muted">
      {children}
    </p>
  );
}
