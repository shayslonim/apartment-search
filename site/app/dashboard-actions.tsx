"use client";

export function DashboardActions() {
  async function signOut() {
    await fetch("/api/session", { method: "DELETE" });
    window.location.reload();
  }

  return (
    <div className="dashboard-actions">
      <button type="button" onClick={() => window.location.reload()}>Refresh</button>
      <button type="button" onClick={signOut}>Lock</button>
    </div>
  );
}
