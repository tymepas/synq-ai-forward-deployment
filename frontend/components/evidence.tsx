import { EvidenceDetail } from "@/lib/api";

export function humanize(value: string) {
  return value.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase()).replace(/\bId\b/g, "ID").replace(/\bKm\b/g, "km");
}

export function EvidenceReviewed({ details = [], citations, title = "Evidence reviewed" }: { details?: EvidenceDetail[]; citations: string[]; title?: string }) {
  const labels = [...new Set(details.map((detail) => detail.label))];
  const rawDetails = details.length ? details : citations.map((citation) => ({ label: "Cited operational record", kind: "operational_record", citation }));

  return <section className="evidence-reviewed" aria-label={title}>
    <p className="eyebrow">EVIDENCE REVIEWED</p><h3>{title}</h3>
    <div className="evidence-chip-grid">
      {labels.length ? labels.map((label) => <span className="evidence-chip" key={label}>{label}</span>) : <span className="evidence-chip">Cited operational records</span>}
    </div>
    <details className="raw-evidence">
      <summary>View evidence details</summary>
      <ul>{rawDetails.map((detail) => <li key={detail.citation}><span>{detail.label}</span><code>{detail.citation}</code></li>)}</ul>
    </details>
  </section>;
}
