import { cookies } from "next/headers";
import { apartmentStats, listApartments } from "@/db/apartments";
import { DASHBOARD_COOKIE, validDashboardSession } from "@/lib/auth";
import { requireEnvironmentValue } from "@/lib/env";
import type { StoredApartment } from "@/lib/types";
import { DashboardActions } from "./dashboard-actions";
import { LoginForm } from "./login-form";

export const dynamic = "force-dynamic";

export default async function Home() {
  const secret = requireEnvironmentValue("DASHBOARD_SECRET");
  const jar = await cookies();
  const authorized = await validDashboardSession(
    jar.get(DASHBOARD_COOKIE)?.value,
    secret,
  );
  if (!authorized) return <LoginForm />;

  const [listings, stats] = await Promise.all([
    listApartments(),
    apartmentStats(),
  ]);

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Apartment Search</p>
          <h1>Match inbox</h1>
        </div>
        <div className="status" title="Hosted webhook receiver is available">
          <span className="status-dot" />
          Receiver online
        </div>
      </header>

      <section className="metrics" aria-label="Search summary">
        <div><strong>{stats.total}</strong><span>Posts received</span></div>
        <div><strong>{stats.strong}</strong><span>Strong matches</span></div>
        <div><strong>{stats.review}</strong><span>Needs review</span></div>
        <div><strong>{stats.averageScore}</strong><span>Average score</span></div>
      </section>

      <section className="results">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Latest posts</p>
            <h2>Ranked for your search</h2>
          </div>
          <DashboardActions />
        </div>

        <div className="listing-table">
          <div className="listing-row listing-header" aria-hidden="true">
            <span>Match</span><span>Listing</span><span>Price</span><span>Protection</span>
          </div>
          {listings.length ? (
            listings.map((listing) => <ListingRow listing={listing} key={listing.id} />)
          ) : (
            <div className="empty-state">
              <strong>No posts received yet</strong>
              <span>The first Groups Watcher delivery will appear here.</span>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}

function ListingRow({ listing }: { listing: StoredApartment }) {
  const safeUrl = safeHttpUrl(listing.post_url);
  const title =
    listing.location_signal === "unknown"
      ? listing.group_name || "Location unclear"
      : listing.location_signal;

  return (
    <article className="listing-row">
      <div className="score-cell">
        <strong>{listing.score}</strong>
        <span>{decisionLabel(listing.decision)}</span>
      </div>
      <div className="listing-copy">
        <h3>
          {safeUrl ? (
            <a className="listing-title-link" href={safeUrl} target="_blank" rel="noreferrer">
              {title}
            </a>
          ) : title}
        </h3>
        <p dir="auto">{listing.body}</p>
        <small>
          {listing.group_name || "Unknown group"}
          {listing.author ? ` · ${listing.author}` : ""}
        </small>
      </div>
      <strong className="price">
        {listing.price_ils
          ? `${listing.price_ils.toLocaleString("en-US")} ILS`
          : "Unknown"}
      </strong>
      <span className={`protection protection-${listing.shelter_signal}`}>
        {protectionLabel(listing.shelter_signal)}
      </span>
    </article>
  );
}

function decisionLabel(decision: StoredApartment["decision"]): string {
  if (decision === "send") return "Strong match";
  if (decision === "review") return "Review";
  return "Low match";
}

function protectionLabel(signal: string): string {
  if (signal === "mamad") return "Mamad";
  if (signal === "shelter") return "Shelter";
  if (signal === "none") return "None";
  return "Unknown";
}

function safeHttpUrl(value: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:"
      ? url.toString()
      : null;
  } catch {
    return null;
  }
}
