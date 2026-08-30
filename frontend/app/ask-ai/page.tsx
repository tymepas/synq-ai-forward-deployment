"use client";

import { FormEvent, useState } from "react";
import { api, TicketResult, VehicleResult } from "@/lib/api";
import { ErrorPanel, PageHeading, StatusPill } from "@/components/ui";

export default function AskAiPage() {
  const [kind, setKind] = useState<"ticket" | "vehicle">("ticket"); const [value, setValue] = useState(""); const [result, setResult] = useState<TicketResult | VehicleResult | null>(null); const [loading, setLoading] = useState(false); const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent) { event.preventDefault(); if (!value.trim()) return; setLoading(true); setError(null); setResult(null); try { setResult(kind === "ticket" ? await api.queryTicket(value.trim()) : await api.vehicle(value.trim())); } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to retrieve evidence."); } finally { setLoading(false); } }
  const ticketResult = result && "ticket" in result ? result : null; const vehicleResult = result && "vehicle" in result ? result : null;
  return <>
    <PageHeading eyebrow="EVIDENCE WORKSPACE" title="Ask AI"><span className="pill neutral">EXPLANATION ASSISTANT PENDING</span></PageHeading>
    <section className="card ai-notice"><div className="ai-symbol">✦</div><div><h2>Grounded evidence lookup</h2><p>The AI explanation phase is intentionally not enabled yet. Search the existing structured backend evidence below; it cannot create dispatch decisions or actions.</p></div></section>
    <form className="query-form card" onSubmit={submit}><label><span>Evidence type</span><select value={kind} onChange={(event) => setKind(event.target.value as "ticket" | "vehicle")}><option value="ticket">Ticket ID</option><option value="vehicle">Vehicle registration</option></select></label><label className="query-input"><span>{kind === "ticket" ? "Ticket ID" : "Vehicle registration"}</span><input value={value} onChange={(event) => setValue(event.target.value)} placeholder={kind === "ticket" ? "e.g. TKT-0020" : "e.g. UP86CM7252"} /></label><button className="button" disabled={loading}>{loading ? "Retrieving…" : "Retrieve evidence"}</button></form>
    {error && <ErrorPanel message={error} />}
    {result && <section className="card answer-card"><div className="card-heading"><div><p className="eyebrow">BACKEND EVIDENCE</p><h2>{ticketResult?.ticket?.ticket_id ? String(ticketResult.ticket.ticket_id) : vehicleResult?.vehicle?.vehicle_reg ?? "Result"}</h2></div><StatusPill value={result.status} /></div>{result.status === "INSUFFICIENT_DATA" ? <p className="insufficient">INSUFFICIENT_DATA: {result.reason ?? "The backend has no grounded evidence for this lookup."}</p> : <><div className="detail-grid">{Object.entries(ticketResult?.ticket ?? vehicleResult?.vehicle ?? {}).map(([key, item]) => <div key={key}><span>{key.replaceAll("_", " ")}</span><strong>{String(item ?? "—")}</strong></div>)}</div>{ticketResult?.decision && <div className="decision-box"><span>Deterministic decision</span><strong>{ticketResult.decision.status ?? "INSUFFICIENT_DATA"}</strong><div className="reason-list">{ticketResult.decision.reason_codes?.map((reason) => <span key={reason}>{reason.replaceAll("_", " ")}</span>)}</div></div>}<p className="citation-line">Evidence: {result.citations.join(" · ") || "No citations available"}</p></>}</section>}
  </>;
}
