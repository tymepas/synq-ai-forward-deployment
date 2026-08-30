"use client";

import { FormEvent, useState } from "react";
import { api, ExplanationResult } from "@/lib/api";
import { ErrorPanel, PageHeading, StatusPill } from "@/components/ui";

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
  return <>
    <PageHeading eyebrow="GROUNDING REQUIRED" title="Ask AI"><span className="pill positive">EXPLANATION ONLY</span></PageHeading>
    <section className="card ai-notice"><div className="ai-symbol">✦</div><div><h2>Evidence-grounded operational assistant</h2><p>GPT explains only the PII-safe structured evidence returned by FastAPI. It cannot make, approve, or alter dispatch decisions.</p></div></section>
    <form className="query-form card explain-form" onSubmit={submit}>
      <label><span>Evidence type</span><select value={kind} onChange={(event) => setKind(event.target.value as "ticket" | "vehicle")}><option value="ticket">Ticket ID</option><option value="vehicle">Vehicle registration</option></select></label>
      <label className="query-input"><span>{kind === "ticket" ? "Ticket ID" : "Vehicle registration"}</span><input required value={lookup} onChange={(event) => setLookup(event.target.value)} placeholder={kind === "ticket" ? "e.g. TKT-0020" : "e.g. UP86CM7252"} /></label>
      <label className="question-input"><span>Operational question</span><input required value={question} maxLength={1000} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask about the evidence or recorded outcome" /></label>
      <button className="button" disabled={loading}>{loading ? "Retrieving evidence…" : "Explain with evidence"}</button>
    </form>
    {error && <ErrorPanel message={error} />}
    {result && <section className="card answer-card"><div className="card-heading"><div><p className="eyebrow">GROUNDED EXPLANATION</p><h2>{summary && "ticket_id" in summary ? String(summary.ticket_id) : summary && "vehicle_reg" in summary ? String(summary.vehicle_reg) : "Operational evidence"}</h2></div><StatusPill value={result.status} /></div>
      {result.status === "INSUFFICIENT_DATA" ? <p className="insufficient">INSUFFICIENT_DATA: {result.reason?.replaceAll("_", " ") ?? "The backend has no grounded evidence for this request."}</p> : <div className="explanation-text">{result.explanation}</div>}
      {summary && <><p className="evidence-label">Structured backend evidence</p><div className="detail-grid">{Object.entries(summary).map(([key, item]) => <div key={key}><span>{key.replaceAll("_", " ")}</span><strong>{String(item ?? "—")}</strong></div>)}</div></>}
      {decision && <div className="decision-box"><span>Recorded deterministic decision</span><strong>{decision.status ?? "INSUFFICIENT_DATA"}</strong><div className="reason-list">{decision.reason_codes?.map((reason) => <span key={reason}>{reason.replaceAll("_", " ")}</span>)}</div></div>}
      <p className="citation-line">Backend evidence citations: {result.citations.join(" · ") || "No citations available"}</p>
    </section>}
  </>;
}
