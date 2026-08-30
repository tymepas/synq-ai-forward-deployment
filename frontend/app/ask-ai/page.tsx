"use client";

import { FormEvent, useMemo, useState } from "react";
import { api, EvidenceDetail, ExplanationResult } from "@/lib/api";
import { ErrorPanel, PageHeading, StatusPill } from "@/components/ui";

const sectionNames = ["Decision", "Why automation stopped", "What we know", "What to do next"] as const;

type ExplanationSection = { title: string; content: string };

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

function splitExplanation(text: string | null): ExplanationSection[] {
  if (!text) return [];
  const sections: ExplanationSection[] = [];
  let current: ExplanationSection | null = null;
  for (const line of text.split("\n")) {
    const match = line.match(/^\s*(?:\*\*)?(Decision|Why automation stopped|What we know|What to do next)(?:\*\*)?\s*:\s*(.*)$/i);
    if (match) {
      current = { title: sectionNames.find((name) => name.toLowerCase() === match[1].toLowerCase()) ?? match[1], content: match[2] };
      sections.push(current);
    } else if (current && line.trim()) {
      current.content = `${current.content}${current.content ? " " : ""}${line.trim()}`;
    }
  }
  return sections.length ? sections : [{ title: "Explanation", content: text }];
}

function EvidencePanel({ details, citations }: { details: EvidenceDetail[]; citations: string[] }) {
  const labels = [...new Set(details.map((detail) => detail.label))];
  return <section className="copilot-evidence" aria-label="Evidence reviewed">
    <div><p className="eyebrow">EVIDENCE REVIEWED</p><h3>Grounded backend records</h3></div>
    <div className="evidence-chip-grid">
      {labels.length ? labels.map((label) => <span className="evidence-chip" key={label}>{label}</span>) : <span className="muted">No evidence labels available</span>}
    </div>
    <details className="raw-evidence">
      <summary>View evidence details</summary>
      <ul>
        {(details.length ? details : citations.map((citation) => ({ label: "Operational record", kind: "operational_record", citation }))).map((detail) => <li key={detail.citation}>
          <span>{detail.label}</span><code>{detail.citation}</code>
        </li>)}
      </ul>
    </details>
  </section>;
}

export default function AskAiPage() {
  const [kind, setKind] = useState<"ticket" | "vehicle">("ticket");
  const [lookup, setLookup] = useState("");
  const [question, setQuestion] = useState("Explain the recorded operational outcome and the evidence supporting it.");
  const [result, setResult] = useState<ExplanationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!lookup.trim() || !question.trim()) return;
    setLoading(true); setError(null); setResult(null);
    try {
      setResult(await api.explain(question.trim(), kind === "ticket" ? lookup.trim() : undefined, kind === "vehicle" ? lookup.trim() : undefined));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The grounded explanation is unavailable.");
    } finally { setLoading(false); }
  }

  const evidence = result?.evidence;
  const summary = evidence && "ticket" in evidence ? evidence.ticket : evidence && "vehicle" in evidence ? evidence.vehicle : undefined;
  const decision = evidence && "decision" in evidence ? evidence.decision : undefined;
  const sections = useMemo(() => splitExplanation(result?.explanation ?? null), [result?.explanation]);
  const citationDetails = evidence?.citation_details ?? [];

  return <>
    <PageHeading eyebrow="OPERATIONS INTELLIGENCE" title="Operations Copilot"><span className="pill positive">AI EXPLANATION ONLY</span></PageHeading>
    <p className="copilot-subtitle">Ask why a decision happened. Get the answer with evidence.</p>
    <section className="card ai-notice copilot-intro"><div className="ai-symbol">✦</div><div><h2>Evidence-led operational guidance</h2><p>Explanations are based only on PII-safe backend records. The deterministic system remains the authority for every dispatch outcome.</p></div></section>
    <form className="query-form card explain-form" onSubmit={submit}>
      <label><span>Evidence type</span><select value={kind} onChange={(event) => setKind(event.target.value as "ticket" | "vehicle")}><option value="ticket">Ticket ID</option><option value="vehicle">Vehicle registration</option></select></label>
      <label className="query-input"><span>{kind === "ticket" ? "Ticket ID" : "Vehicle registration"}</span><input required value={lookup} onChange={(event) => setLookup(event.target.value)} placeholder={kind === "ticket" ? "e.g. TKT-0001" : "e.g. UP86CM7252"} /></label>
      <label className="question-input"><span>Operational question</span><input required value={question} maxLength={1000} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask about the evidence or recorded outcome" /></label>
      <button className="button" disabled={loading}>{loading ? "Retrieving evidence…" : "Explain with evidence"}</button>
    </form>
    {error && <ErrorPanel message={error} />}
    {result && <section className="card answer-card copilot-result">
      <div className="card-heading"><div><p className="eyebrow">OPERATIONS EXPLANATION</p><h2>{summary && "ticket_id" in summary ? String(summary.ticket_id) : summary && "vehicle_reg" in summary ? String(summary.vehicle_reg) : "Operational evidence"}</h2></div><StatusPill value={result.status} /></div>
      {decision && <div className="decision-strip"><div><span>Recorded deterministic decision</span><strong>{decision.status ?? "INSUFFICIENT_DATA"}</strong></div><div className="reason-list">{decision.reason_codes?.map((reason) => <span key={reason}>{formatLabel(reason)}</span>)}</div></div>}
      {result.status === "INSUFFICIENT_DATA" ? <p className="insufficient">INSUFFICIENT_DATA: {result.reason?.replaceAll("_", " ") ?? "The backend has no grounded evidence for this request."}</p> : <div className="copilot-sections">{sections.map((section) => <section className={`copilot-section ${section.title === "What to do next" ? "next-action" : ""}`} key={section.title}><h3>{section.title}</h3><p>{section.content || "INSUFFICIENT_DATA"}</p></section>)}</div>}
      {summary && <section className="copilot-facts"><p className="eyebrow">RECORDED FACTS</p><div className="detail-grid">{Object.entries(summary).map(([key, item]) => <div key={key}><span>{formatLabel(key)}</span><strong>{String(item ?? "—")}</strong></div>)}</div></section>}
      <EvidencePanel details={citationDetails} citations={result.citations} />
    </section>}
  </>;
}
