"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ErrorPanel, LoadingPanel, MetricCard, PageHeading, StatusPill } from "@/components/ui";

type DashboardData = { tickets: number; vehicles: number; approvals: number; quarantine: number; healthy: boolean; databaseReady: boolean };

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [health, tickets, vehicles, approvals, quarantine] = await Promise.all([api.health(), api.tickets(), api.vehicles(), api.approvals(), api.quarantine()]);
      setData({ tickets: tickets.count, vehicles: vehicles.count, approvals: approvals.count, quarantine: quarantine.count, healthy: health.status === "ok", databaseReady: health.database_ready });
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to load the operations overview."); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function runPipeline() {
    setSyncing(true); setError(null);
    try { await api.run(); await load(); } catch (caught) { setError(caught instanceof Error ? caught.message : "The operational run was not completed."); } finally { setSyncing(false); }
  }

  return <>
    <PageHeading eyebrow="LIVE CONTROL" title="Operations at a glance">
      <button className="button" onClick={runPipeline} disabled={syncing}>{syncing ? "Running pipeline…" : "Run pipeline"}</button>
    </PageHeading>
    {error && <ErrorPanel message={error} onRetry={load} />}
    {!data && !error && <LoadingPanel label="Loading operations overview…" />}
    {data && <>
      <section className="metrics-grid" aria-label="Operational metrics">
        <MetricCard label="Canonical tickets" value={data.tickets} detail="Validated, deduplicated operational tickets" />
        <MetricCard label="Pending approvals" value={data.approvals} detail="Actions awaiting human review" tone="orange" />
        <MetricCard label="Fleet records" value={data.vehicles} detail="Canonicalized fleet entities" tone="purple" />
        <MetricCard label="Quarantined" value={data.quarantine} detail="Records intentionally isolated from automation" tone="green" />
      </section>
      <section className="split-grid top-gap">
        <article className="card health-card">
          <div className="card-heading"><div><p className="eyebrow">SERVICE STATUS</p><h2>Backend connection</h2></div><StatusPill value={data.healthy ? "HEALTHY" : "UNAVAILABLE"} /></div>
          <div className="health-row"><span className={data.databaseReady ? "status-dot online" : "status-dot"} /><span>SQLite context</span><strong>{data.databaseReady ? "Ready" : "Initializing"}</strong></div>
          <p className="muted">Every action is backed by the FastAPI service. The interface never evaluates dispatch rules locally.</p>
        </article>
        <article className="card">
          <div className="card-heading"><div><p className="eyebrow">OPERATOR QUEUE</p><h2>Review next</h2></div></div>
          <p className="queue-number">{data.approvals}</p><p className="muted">Actions awaiting authorized human review before the local outbox step.</p>
          <Link className="text-link" href="/approvals">Open approval queue →</Link>
        </article>
      </section>
      <section className="card top-gap safety-card">
        <div><p className="eyebrow">SAFETY MODEL</p><h2>Deterministic by design</h2><p className="muted">Human approval protects irreversible actions. PII is minimized, and missing operational evidence remains a safe manual hold.</p></div>
        <div className="safety-items"><span>Human approval</span><span>Exactly once</span><span>PII minimized</span></div>
      </section>
    </>}
  </>;
}
