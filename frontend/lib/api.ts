export type TicketListItem = { ticket_id: string; normalized_vehicle: string; created_at: string };
export type Vehicle = { vehicle_reg: string; vehicle_id?: string | null; model?: string | null; year?: number | null; bs_stage?: string | null; engine_heater?: string | null; home_hub?: string | null; capacity_tonnes?: number | null; fleet_status?: string | null; resolution_status?: string | null };
export type Approval = { message_id: string; ticket_id: string; approval_context: { decision_status?: string; reason_codes?: string[]; work_order_id?: string }; citations: string[] };
export type EvidenceDetail = { label: string; kind: string; citation: string };
export type QuarantineItem = { quarantine_id: string; ticket_id: string | null; reasons: string[]; summary: Record<string, unknown> };
export type TicketResult = { status: string; reason?: string; ticket?: Record<string, unknown>; work_order_id?: string | null; pending_message_id?: string | null; decision?: { status?: string; reason_codes?: string[]; candidate_results?: Record<string, unknown> }; citations: string[]; citation_details?: EvidenceDetail[] };
export type VehicleResult = { status: string; reason?: string; vehicle?: Vehicle; conflicts?: { field_name: string; material: boolean; resolution_status: string }[]; citations: string[]; citation_details?: EvidenceDetail[] };
export type ExplanationResult = { status: "EXPLAINED" | "INSUFFICIENT_DATA"; explanation: string | null; reason: string | null; citations: string[]; evidence: TicketResult | VehicleResult };

class ApiError extends Error {
  constructor(message: string, readonly status: number) { super(message); }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, { ...init, headers: { "Content-Type": "application/json", ...init?.headers }, cache: "no-store" });
  } catch {
    throw new ApiError("Check that the FastAPI backend is running and BACKEND_URL is configured.", 0);
  }
  if (!response.ok) {
    throw new ApiError(response.status === 422 ? "The backend rejected this request safely." : "The backend request failed.", response.status);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; service: string; database_ready: boolean }>("/health"),
  run: () => request<{ status: string; processing: { processed: number; manual_holds: number; replacements: number } }>("/run", { method: "POST", body: "{}" }),
  tickets: () => request<{ tickets: TicketListItem[]; count: number }>("/tickets"),
  ticket: (id: string) => request<TicketResult>(`/ticket/${encodeURIComponent(id)}`),
  vehicles: () => request<{ vehicles: Vehicle[]; count: number }>("/vehicles"),
  vehicle: (id: string) => request<VehicleResult>("/query", { method: "POST", body: JSON.stringify({ vehicle_reg: id }) }),
  queryTicket: (id: string) => request<TicketResult>("/query", { method: "POST", body: JSON.stringify({ ticket_id: id }) }),
  explain: (question: string, ticketId?: string, vehicleReg?: string) => request<ExplanationResult>("/explain", {
    method: "POST", body: JSON.stringify({ question, ...(ticketId ? { ticket_id: ticketId } : { vehicle_reg: vehicleReg }) }),
  }),
  approvals: () => request<{ approvals: Approval[]; count: number }>("/approvals/pending"),
  approve: (ticketId: string, approvedBy: string) => request<{ ticket_id: string; message_id: string; created: boolean }>("/approve", { method: "POST", body: JSON.stringify({ ticket_id: ticketId, approved_by: approvedBy, approved_at: new Date().toISOString() }) }),
  quarantine: () => request<{ quarantine: QuarantineItem[]; count: number }>("/quarantine"),
};

export { ApiError };
