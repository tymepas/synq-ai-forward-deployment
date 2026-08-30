"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { EvidenceReviewed, humanize } from "@/components/evidence";
import { api, TicketListItem, TicketResult } from "@/lib/api";
import { EmptyPanel, ErrorPanel, LoadingPanel, PageHeading, StatusPill } from "@/components/ui";

const factKeys = ["vehicle_normalized", "driver_id", "origin_hub", "destination", "client", "issue", "created_at"];

export default function TicketsPage() {
  const [tickets, setTickets] = useState<TicketListItem[]>([]); const [selected, setSelected] = useState<TicketResult | null>(null);
  const [search, setSearch] = useState(""); const [date, setDate] = useState(""); const [loading, setLoading] = useState(true); const [inspecting, setInspecting] = useState(false); const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => { setLoading(true); setError(null); try { setTickets((await api.tickets()).tickets); } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to load tickets."); } finally { setLoading(false); } }, []);
  useEffect(() => { void load(); }, [load]);
  const filtered = useMemo(() => tickets.filter((ticket) => `${ticket.ticket_id} ${ticket.normalized_vehicle}`.toLowerCase().includes(search.toLowerCase()) && (!date || ticket.created_at.startsWith(date))), [tickets, search, date]);
  async function inspect(id: string) { setInspecting(true); setError(null); try { setSelected(await api.ticket(id)); } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to inspect this ticket."); } finally { setInspecting(false); } }
  const ticket = selected?.ticket ?? {};
  const facts: Array<[string, unknown]> = factKeys.filter((key) => key in ticket).map((key) => [key, ticket[key]]);
  return <>
    <PageHeading eyebrow="TICKET REGISTER" title="Breakdown tickets"><p className="page-count">{filtered.length} shown</p></PageHeading>
    <div className="toolbar"><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search ticket or vehicle" aria-label="Search tickets" /><input type="date" value={date} onChange={(event) => setDate(event.target.value)} aria-label="Filter by date" /><button className="button secondary" onClick={() => { setSearch(""); setDate(""); }}>Clear filters</button></div>
    {loading ? <LoadingPanel /> : error ? <ErrorPanel message={error} onRetry={load} /> : filtered.length === 0 ? <EmptyPanel title="No matching tickets" detail="Adjust the search or date filter to review another record." /> :
      <div className="card table-card"><div className="table-scroll"><table><thead><tr><th>Ticket</th><th>Vehicle</th><th>Created</th><th>Decision</th><th /></tr></thead><tbody>{filtered.map((item) => <tr key={item.ticket_id}><td><strong>{item.ticket_id}</strong></td><td>{item.normalized_vehicle}</td><td>{new Date(item.created_at).toLocaleString()}</td><td>{selected?.ticket?.ticket_id === item.ticket_id ? <StatusPill value={selected.decision?.status} /> : <span className="muted">Inspect to view</span>}</td><td><button className="table-action" onClick={() => inspect(item.ticket_id)} disabled={inspecting}>{inspecting ? "Loading…" : "Inspect"}</button></td></tr>)}</tbody></table></div></div>}
    {inspecting && <LoadingPanel label="Loading ticket evidence…" />}
    {selected && <section className="card detail-card ticket-detail"><div className="card-heading"><div><p className="eyebrow">TICKET DETAIL</p><h2>{String(ticket.ticket_id ?? "Ticket")}</h2></div><StatusPill value={selected.decision?.status ?? selected.status} /></div>
      <div className="ticket-summary-grid"><div><span>Current decision</span><strong>{humanize(selected.decision?.status ?? selected.status)}</strong></div><div><span>Severity</span><strong>{String(ticket.severity ?? "Unavailable")}</strong></div><div><span>Status</span><strong>{String(ticket.status ?? "Unavailable")}</strong></div></div>
      <section className="detail-section"><p className="eyebrow">OPERATIONAL FACTS</p><h3>Recorded ticket context</h3><div className="detail-grid">{facts.map(([key, value]) => <div key={key}><span>{humanize(key)}</span><strong>{String(value ?? "—")}</strong></div>)}</div></section>
      <section className="decision-summary"><p className="eyebrow">DECISION / REASON</p><h3>{humanize(selected.decision?.status ?? selected.status)}</h3><div className="reason-list">{selected.decision?.reason_codes?.map((reason) => <span key={reason}>{humanize(reason)}</span>) ?? <span>No recorded reason</span>}</div></section>
      <EvidenceReviewed details={selected.citation_details} citations={selected.citations} />
    </section>}
  </>;
}
