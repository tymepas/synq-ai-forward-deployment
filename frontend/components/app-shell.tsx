"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const navigation = [
  ["Overview", "/", "◈"],
  ["Tickets", "/tickets", "▤"],
  ["Approvals", "/approvals", "✓"],
  ["Vehicles", "/vehicles", "▱"],
  ["Quarantine", "/quarantine", "!"],
  ["Operations Copilot", "/ask-ai", "✦"],
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <div className="app-frame">
      <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
        <Link href="/" className="brand" onClick={() => setOpen(false)}>
          <span className="brand-mark">M</span>
          <span><strong>Meridian</strong><small>CONTROL CENTER</small></span>
        </Link>
        <nav aria-label="Primary navigation">
          {navigation.map(([label, href, icon]) => (
            <Link key={href} href={href} onClick={() => setOpen(false)} className={pathname === href ? "nav-link active" : "nav-link"}>
              <span aria-hidden="true">{icon}</span>{label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-foot"><span className="live-dot" />Deterministic operations</div>
      </aside>
      <main className="content">
        <header className="topbar">
          <button className="menu-button" onClick={() => setOpen(!open)} aria-label="Toggle navigation">☰</button>
          <div><p className="eyebrow">MERIDIAN FREIGHT</p><p className="topbar-title">Operations workspace</p></div>
          <div className="safe-mode"><span className="shield">◆</span> Safe mode</div>
        </header>
        <div className="page-content">{children}</div>
      </main>
    </div>
  );
}
