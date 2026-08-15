import { cookies } from "next/headers";
import { apartmentStats, listApartments } from "@/db/apartments";
import { DASHBOARD_COOKIE, validDashboardSession } from "@/lib/auth";
import { requireEnvironmentValue } from "@/lib/env";
import type { Category, StoredApartment } from "@/lib/types";
import { DashboardActions } from "./dashboard-actions";
import { LoginForm } from "./login-form";

export const dynamic = "force-dynamic";

const CATEGORY_ORDER: Category[] = ["recommended", "just_okay", "not_really"];

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
          <h1>AI-ranked results</h1>
        </div>
        <div className="status" title="Hosted receiver is available">
          <span className="status-dot" />
          Receiver online{stats.queued ? ` · ${stats.queued} awaiting analysis` : ""}
        </div>
      </header>

      <section className="metrics" aria-label="Search summary">
        <Metric value={stats.total} label="Posts received" />
        <Metric value={stats.recommended} label="Recommended" />
        <Metric value={stats.justOkay} label="Just Okay" />
        <Metric value={stats.notReally} label="Not Really" />
        <Metric value={stats.queued} label="Analysis queue" />
        <Metric value={stats.failed} label="Needs retry" />
      </section>

      <section className="results">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Local AI analysis</p>
            <h2>Every completed listing</h2>
          </div>
          <DashboardActions />
        </div>

        {CATEGORY_ORDER.map((category) => (
          <CategorySection
            category={category}
            key={category}
            listings={listings.filter((listing) => listing.decision === category)}
          />
        ))}
      </section>
      <footer className="map-attribution">
        Location and walking-route data ©{" "}
        <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">
          OpenStreetMap contributors
        </a>
      </footer>
    </main>
  );
}

function Metric({ value, label }: { value: number; label: string }) {
  return <div><strong>{value}</strong><span>{label}</span></div>;
}

function CategorySection({
  category,
  listings,
}: {
  category: Category;
  listings: StoredApartment[];
}) {
  return (
    <section className={`category-section category-${category}`}>
      <div className="category-heading">
        <h2>{categoryLabel(category)}</h2>
        <span>{listings.length}</span>
      </div>
      {listings.length ? (
        <div className="listing-table">
          <div className="listing-row listing-header" aria-hidden="true">
            <span>Match</span><span>Listing</span><span>Price</span><span>Walking</span><span>Protection</span>
          </div>
          {listings.map((listing) => <ListingRow listing={listing} key={listing.id} />)}
        </div>
      ) : (
        <div className="empty-category">No listings in this category yet.</div>
      )}
    </section>
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
        <span>{categoryLabel(listing.decision)}</span>
      </div>
      <div className="listing-copy">
        <h3>
          {safeUrl ? (
            <a className="listing-title-link" href={safeUrl} target="_blank" rel="noreferrer">
              {title}
            </a>
          ) : title}
        </h3>
        <p className="analysis-summary" dir="auto">{listing.summary}</p>
        <p className="post-body" dir="auto">{listing.body}</p>
        <small>
          {listing.group_name || "Unknown group"}
          {listing.author ? ` · ${listing.author}` : ""}
          {listing.analysis_model ? ` · ${listing.analysis_model}` : ""}
        </small>
      </div>
      <strong className="price">
        {listing.price_ils
          ? `${listing.price_ils.toLocaleString("en-US")} ILS`
          : "Unknown"}
      </strong>
      <div className="walking-cell">
        <Walk label="Work" minutes={listing.walk_to_work_minutes} meters={listing.walk_to_work_meters} />
        <Walk label="Sarona" minutes={listing.walk_to_sarona_minutes} meters={listing.walk_to_sarona_meters} />
      </div>
      <span className={`protection protection-${listing.shelter_signal}`}>
        {protectionLabel(listing.shelter_signal)}
      </span>
    </article>
  );
}

function Walk({
  label,
  minutes,
  meters,
}: {
  label: string;
  minutes: number | null;
  meters: number | null;
}) {
  return (
    <span>
      <strong>{label}</strong>
      {minutes === null ? "Unknown" : `${minutes} min${meters === null ? "" : ` · ${distanceLabel(meters)}`}`}
    </span>
  );
}

function distanceLabel(meters: number): string {
  return meters < 1000 ? `${meters} m` : `${(meters / 1000).toFixed(1)} km`;
}

function categoryLabel(category: Category): string {
  if (category === "recommended") return "Recommended";
  if (category === "just_okay") return "Just Okay";
  return "Not Really";
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
