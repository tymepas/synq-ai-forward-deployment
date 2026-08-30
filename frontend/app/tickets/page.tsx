"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, TicketListItem, TicketResult } from "@/lib/api";
import { EmptyPanel, ErrorPanel, LoadingPanel, PageHeading, StatusPill } from "@/components/ui";

export default function TicketsPage() {
  const [tickets, setTickets] = useState<TicketListItem[]>([]); const [selected, setSelected] = useState<TicketResult | null>(null);
  const [search, setSearch] = useState(""); const [date, setDate] = useState(""); const [loading, setLoading] = useState(true); const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => { setLoading(true); setError(null); try { setTickets((await api.tickets()).tickets); } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to load tickets."); } finally { setLoading(false); } }, []);
  useEffect(() => { void load(); }, [load]);
  const filtered = useMemo(() => tickets.filter((ticket) => `${ticket.ticket_id} ${ticket.normalized_vehicle}`.toLowerCase().includes(search.toLowerCase()) && (!date || ticket.created_at.startsWith(date))), [tickets, search, date]);
  async function inspect(id: string) { try { setSelected(await api.ticket(id)); } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to inspect this ticket."); } }
  return <>
    <PageHeading eyebrow="TICKET REGISTER" title="Breakdown tickets"><p className="page-count">{filtered.length} shown</p></PageHeading>
    <div className="toolbar"><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search ticket or vehicle" aria-label="Search tickets" /><input type="date" value={date} onChange={(event) => setDate(event.target.value)} aria-label="Filter by date" /><button className="button secondary" onClick={() => { setSearch(""); setDate(""); }}>Clear filters</button></div>
    {loading ? <LoadingPanel /> : error ? <ErrorPanel message={error} onRetry={load} /> : filtered.length === 0 ? <EmptyPanel title="No matching tickets" detail="Adjust the search or date filter to review another record." /> :
      <div className="card table-card"><div className="table-scroll"><table><thead><tr><th>Ticket</th><th>Vehicle</th><th>Created</th><th>Decision</th><th /></tr></thead><tbody>{filtered.map((ticket) => <tr key={ticket.ticket_id}><td><strong>{ticket.ticket_id}</strong></td><td>{ticket.normalized_vehicle}</td><td>{new Date(ticket.created_at).toLocaleString()}</td><td><StatusPill value={selected?.ticket?.ticket_id === ticket.ticket_id ? selected.decision?.status : "READY"} /></td><td><button className="table-action" onClick={() => inspect(ticket.ticket_id)}>Inspect</button></td></tr>)}</tbody></table></div></div>}
    {selected && <section className="card detail-card"><div className="card-heading"><div><p className="eyebrow">CITED TICKET DETAIL</p><h2>{String(selected.ticket?.ticket_id ?? "Ticket")}</h2></div><StatusPill value={selected.decision?.status ?? selected.status} /></div><div className="detail-grid">{Object.entries(selected.ticket ?? {}).map(([key, value]) => <div key={key}><span>{key.replaceAll("_", " ")}</span><strong>{String(value ?? "—")}</strong></div>)}</div><div className="reason-list">{selected.decision?.reason_codes?.map((reason) => <span key={reason}>{reason.replaceAll("_", " ")}</span>)}</div><p className="citation-line">Evidence: {selected.citations.join(" · ") || "No citations available"}</p></section>}
  </>;
}
