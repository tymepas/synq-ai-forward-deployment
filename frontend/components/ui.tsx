export function LoadingPanel({ label = "Loading operational data…" }: { label?: string }) {
  return <div className="state-panel"><span className="spinner" aria-hidden="true" />{label}</div>;
}

export function ErrorPanel({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="state-panel error-panel"><span>!</span><div><strong>Unable to load data</strong><p>{message}</p></div>{onRetry && <button className="button secondary" onClick={onRetry}>Try again</button>}</div>;
}

export function EmptyPanel({ title, detail }: { title: string; detail: string }) {
  return <div className="empty-panel"><div className="empty-icon">○</div><strong>{title}</strong><p>{detail}</p></div>;
}

export function StatusPill({ value }: { value: string | null | undefined }) {
  const normal = value?.toUpperCase() ?? "UNKNOWN";
  const tone = normal.includes("PASS") || normal.includes("FOUND") || normal.includes("RESOLVED") || normal.includes("SENT")
    ? "positive" : normal.includes("HOLD") || normal.includes("PENDING") || normal.includes("INSUFFICIENT") ? "warning" : "neutral";
  return <span className={`pill ${tone}`}>{value?.replaceAll("_", " ") ?? "UNKNOWN"}</span>;
}

export function MetricCard({ label, value, detail, tone = "blue" }: { label: string; value: number | string; detail: string; tone?: "blue" | "orange" | "purple" | "green" }) {
  return <article className={`metric-card ${tone}`}><p>{label}</p><strong>{value}</strong><span>{detail}</span></article>;
}

export function PageHeading({ eyebrow, title, children }: { eyebrow: string; title: string; children?: React.ReactNode }) {
  return <div className="page-heading"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1></div>{children}</div>;
}
