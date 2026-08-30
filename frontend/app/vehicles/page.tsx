"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, Vehicle, VehicleResult } from "@/lib/api";
import { EmptyPanel, ErrorPanel, LoadingPanel, PageHeading, StatusPill } from "@/components/ui";

export default function VehiclesPage() {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]); const [search, setSearch] = useState(""); const [status, setStatus] = useState("ALL"); const [selected, setSelected] = useState<VehicleResult | null>(null); const [loading, setLoading] = useState(true); const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => { setLoading(true); setError(null); try { setVehicles((await api.vehicles()).vehicles); } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to load vehicle records."); } finally { setLoading(false); } }, []);
  useEffect(() => { void load(); }, [load]);
  const statuses = useMemo(() => ["ALL", ...Array.from(new Set(vehicles.map((vehicle) => vehicle.fleet_status).filter(Boolean)))], [vehicles]);
  const filtered = useMemo(() => vehicles.filter((vehicle) => `${vehicle.vehicle_reg} ${vehicle.model ?? ""} ${vehicle.home_hub ?? ""}`.toLowerCase().includes(search.toLowerCase()) && (status === "ALL" || vehicle.fleet_status === status)), [vehicles, search, status]);
  async function inspect(vehicleReg: string) { try { setSelected(await api.vehicle(vehicleReg)); } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to inspect this vehicle."); } }
  return <>
    <PageHeading eyebrow="FLEET CONTEXT" title="Vehicle lookup"><p className="page-count">{filtered.length} shown</p></PageHeading>
    <div className="toolbar"><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search registration, model or hub" aria-label="Search vehicles" /><select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Filter fleet status">{statuses.map((option) => <option key={option}>{option}</option>)}</select><button className="button secondary" onClick={() => { setSearch(""); setStatus("ALL"); }}>Clear filters</button></div>
    {loading ? <LoadingPanel /> : error ? <ErrorPanel message={error} onRetry={load} /> : filtered.length === 0 ? <EmptyPanel title="No matching vehicles" detail="Adjust the registration, hub, or fleet-status filter." /> : <div className="card table-card"><div className="table-scroll"><table><thead><tr><th>Registration</th><th>Model</th><th>Year</th><th>Home hub</th><th>Fleet status</th><th /></tr></thead><tbody>{filtered.map((vehicle) => <tr key={vehicle.vehicle_reg}><td><strong>{vehicle.vehicle_reg}</strong></td><td>{vehicle.model ?? "—"}</td><td>{vehicle.year ?? "—"}</td><td>{vehicle.home_hub ?? "—"}</td><td><StatusPill value={vehicle.fleet_status} /></td><td><button className="table-action" onClick={() => inspect(vehicle.vehicle_reg)}>Inspect</button></td></tr>)}</tbody></table></div></div>}
    {selected && <section className="card detail-card"><div className="card-heading"><div><p className="eyebrow">CITED VEHICLE DETAIL</p><h2>{selected.vehicle?.vehicle_reg ?? "Vehicle"}</h2></div><StatusPill value={selected.status} /></div><div className="detail-grid">{Object.entries(selected.vehicle ?? {}).map(([key, value]) => <div key={key}><span>{key.replaceAll("_", " ")}</span><strong>{String(value ?? "—")}</strong></div>)}</div>{selected.conflicts && selected.conflicts.length > 0 && <div className="conflict-block"><strong>Recorded conflicts</strong>{selected.conflicts.map((conflict) => <p key={conflict.field_name}>{conflict.field_name}: {conflict.resolution_status} {conflict.material ? "(material)" : ""}</p>)}</div>}<p className="citation-line">Evidence: {selected.citations.join(" · ") || "No citations available"}</p></section>}
  </>;
}
