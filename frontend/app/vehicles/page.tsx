"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { EvidenceReviewed, humanize } from "@/components/evidence";
import { api, Vehicle, VehicleResult } from "@/lib/api";
import { EmptyPanel, ErrorPanel, LoadingPanel, PageHeading, StatusPill } from "@/components/ui";

const vehicleFacts = ["vehicle_id", "model", "year", "home_hub", "capacity_tonnes", "bs_stage", "engine_heater"];

export default function VehiclesPage() {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]); const [search, setSearch] = useState(""); const [status, setStatus] = useState("ALL"); const [selected, setSelected] = useState<VehicleResult | null>(null); const [loading, setLoading] = useState(true); const [inspecting, setInspecting] = useState(false); const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => { setLoading(true); setError(null); try { setVehicles((await api.vehicles()).vehicles); } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to load vehicle records."); } finally { setLoading(false); } }, []);
  useEffect(() => { void load(); }, [load]);
  const statuses = useMemo(() => ["ALL", ...Array.from(new Set(vehicles.map((vehicle) => vehicle.fleet_status).filter(Boolean)))], [vehicles]);
  const filtered = useMemo(() => vehicles.filter((vehicle) => `${vehicle.vehicle_reg} ${vehicle.model ?? ""} ${vehicle.home_hub ?? ""}`.toLowerCase().includes(search.toLowerCase()) && (status === "ALL" || vehicle.fleet_status === status)), [vehicles, search, status]);
  async function inspect(vehicleReg: string) { setInspecting(true); setError(null); try { setSelected(await api.vehicle(vehicleReg)); } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to inspect this vehicle."); } finally { setInspecting(false); } }
  const vehicle: Vehicle = selected?.vehicle ?? { vehicle_reg: "Vehicle" };
  return <>
    <PageHeading eyebrow="FLEET CONTEXT" title="Vehicle lookup"><p className="page-count">{filtered.length} shown</p></PageHeading>
    <div className="toolbar"><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search registration, model or hub" aria-label="Search vehicles" /><select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Filter fleet status">{statuses.map((option) => <option key={option}>{option}</option>)}</select><button className="button secondary" onClick={() => { setSearch(""); setStatus("ALL"); }}>Clear filters</button></div>
    {loading ? <LoadingPanel /> : error ? <ErrorPanel message={error} onRetry={load} /> : filtered.length === 0 ? <EmptyPanel title="No matching vehicles" detail="Adjust the registration, model, hub, or fleet-status filter." /> : <div className="card table-card"><div className="table-scroll"><table><thead><tr><th>Registration</th><th>Model</th><th>Year</th><th>Home hub</th><th>Fleet status</th><th /></tr></thead><tbody>{filtered.map((item) => <tr key={item.vehicle_reg}><td><strong>{item.vehicle_reg}</strong></td><td>{item.model ?? "Unavailable"}</td><td>{item.year ?? "Unavailable"}</td><td>{item.home_hub ?? "Unavailable"}</td><td><StatusPill value={item.fleet_status} /></td><td><button className="table-action" onClick={() => inspect(item.vehicle_reg)} disabled={inspecting}>{inspecting ? "Loading…" : "Inspect"}</button></td></tr>)}</tbody></table></div></div>}
    {inspecting && <LoadingPanel label="Loading vehicle evidence…" />}
    {selected && <section className="card detail-card vehicle-detail"><div className="card-heading"><div><p className="eyebrow">VEHICLE DETAIL</p><h2>{vehicle.vehicle_reg ?? "Vehicle"}</h2></div><StatusPill value={vehicle.fleet_status ?? selected.status} /></div>
      <div className="ticket-summary-grid"><div><span>Fleet status</span><strong>{humanize(vehicle.fleet_status ?? "Unavailable")}</strong></div><div><span>Conflict status</span><strong>{humanize(vehicle.resolution_status ?? "Unavailable")}</strong></div><div><span>Home hub</span><strong>{String(vehicle.home_hub ?? "Unavailable")}</strong></div></div>
      <section className="detail-section"><p className="eyebrow">VEHICLE IDENTITY</p><h3>Recorded fleet context</h3><div className="detail-grid">{vehicleFacts.filter((key) => key in vehicle).map((key) => <div key={key}><span>{humanize(key)}</span><strong>{String(vehicle[key as keyof Vehicle] ?? "Unavailable")}</strong></div>)}</div></section>
      <section className="decision-summary"><p className="eyebrow">OPERATIONAL CONSTRAINTS</p><h3>{selected.conflicts?.length ? "Conflicting or unresolved attributes" : "No recorded attribute conflicts"}</h3>{selected.conflicts?.length ? <div className="reason-list">{selected.conflicts.map((conflict) => <span key={conflict.field_name}>{humanize(conflict.field_name)}: {humanize(conflict.resolution_status)}</span>)}</div> : <p className="muted">Only the verified fleet attributes above are available for downstream rules.</p>}</section>
      <EvidenceReviewed details={selected.citation_details} citations={selected.citations} />
    </section>}
  </>;
}
