"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, QuarantineItem } from "@/lib/api";
import { EmptyPanel, ErrorPanel, LoadingPanel, PageHeading } from "@/components/ui";

export default function QuarantinePage() {
  const [items, setItems] = useState<QuarantineItem[]>([]); const [search, setSearch] = useState(""); const [loading, setLoading] = useState(true); const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => { setLoading(true); setError(null); try { setItems((await api.quarantine()).quarantine); } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to load quarantine records."); } finally { setLoading(false); } }, []);
  useEffect(() => { void load(); }, [load]);
  const filtered = useMemo(() => items.filter((item) => `${item.ticket_id ?? "file-level record"} ${item.reasons.join(" ")}`.toLowerCase().includes(search.toLowerCase())), [items, search]);
  return <>
    <PageHeading eyebrow="SAFE EXCEPTIONS" title="Quarantine"><p className="page-count">{filtered.length} record{filtered.length === 1 ? "" : "s"}</p></PageHeading>
    <p className="page-intro">Invalid inputs are retained with safe reason codes. They are not silently dropped or processed.</p><div className="toolbar single"><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search ticket or reason code" aria-label="Search quarantine" /></div>
    {loading ? <LoadingPanel /> : error ? <ErrorPanel message={error} onRetry={load} /> : filtered.length === 0 ? <EmptyPanel title="No quarantine records" detail="The currently loaded data has no invalid or ambiguous inputs." /> : <section className="quarantine-list">{filtered.map((item) => <article className="card quarantine-card" key={item.quarantine_id}><div className="card-heading"><div><p className="eyebrow">{item.quarantine_id}</p><h2>{item.ticket_id ?? "File-level quarantine"}</h2></div><span className="pill warning">QUARANTINED</span></div><div className="reason-list">{item.reasons.map((reason) => <span key={reason}>{reason.replaceAll("_", " ")}</span>)}</div><details><summary>Safe record summary</summary><pre>{JSON.stringify(item.summary, null, 2)}</pre></details></article>)}</section>}
  </>;
}
