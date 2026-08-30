"use client";

import { useCallback, useEffect, useState } from "react";
import { EvidenceReviewed, humanize } from "@/components/evidence";
import { api, Approval } from "@/lib/api";
import { EmptyPanel, ErrorPanel, LoadingPanel, PageHeading, StatusPill } from "@/components/ui";

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<Approval[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState<string | null>(null); const [saving, setSaving] = useState<string | null>(null); const [notice, setNotice] = useState<string | null>(null);
  const load = useCallback(async () => { setLoading(true); setError(null); try { setApprovals((await api.approvals()).approvals); } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to load approvals."); } finally { setLoading(false); } }, []);
  useEffect(() => { void load(); }, [load]);
  async function approve(ticketId: string) { setSaving(ticketId); setError(null); try { const result = await api.approve(ticketId, "role-dispatch"); setNotice(result.created ? `${ticketId} moved to the local sent outbox.` : `${ticketId} was already approved.`); await load(); } catch (caught) { setError(caught instanceof Error ? caught.message : "Approval was not completed."); } finally { setSaving(null); } }
  return <>
    <PageHeading eyebrow="HUMAN IN THE LOOP" title="Pending approvals"><p className="page-count">{approvals.length} awaiting review</p></PageHeading>
    <p className="page-intro">Human review is required before the local outbox step. No external message is sent by this application.</p>{notice && <div className="notice">{notice}</div>}
    {loading ? <LoadingPanel /> : error ? <ErrorPanel message={error} onRetry={load} /> : approvals.length === 0 ? <EmptyPanel title="No pending approvals" detail="All available messages have been reviewed, or run the pipeline to process new tickets." /> : <section className="approval-grid">{approvals.map((approval) => <article className="card approval-card" key={approval.message_id}><div className="card-heading"><div><p className="eyebrow">HUMAN REVIEW REQUIRED</p><h2>{approval.ticket_id}</h2></div><StatusPill value={approval.approval_context.decision_status ?? "PENDING"} /></div><p className="work-order">Recorded work order: <strong>{approval.approval_context.work_order_id ?? "Unavailable"}</strong></p><section className="approval-reason"><strong>Why approval is required</strong><p>Automation stopped safely because required operational evidence was unavailable. A human review is required before recording the local outbox action.</p><div className="reason-list">{approval.approval_context.reason_codes?.map((reason) => <span key={reason}>{humanize(reason)}</span>)}</div></section><EvidenceReviewed citations={approval.citations} title="Evidence available" /><button className="button full-width" onClick={() => approve(approval.ticket_id)} disabled={saving === approval.ticket_id}>{saving === approval.ticket_id ? "Recording approval…" : "Approve for local outbox"}</button></article>)}</section>}
  </>;
}
