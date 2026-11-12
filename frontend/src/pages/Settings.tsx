import { ProvenancePill } from "../components/ProvenancePill";
import { DEMO_SNAPSHOT_LABEL } from "../utils/dates";

export function Settings() {
  return (
    <>
      <header className="page-header">
        <h1>Settings</h1>
        <p className="subtitle">Demo configuration (read-only)</p>
      </header>
      <section className="card" style={{ maxWidth: 560 }}>
        <h2 className="card-title">Demo identity</h2>
        <p>Summit Retail Co. — single-tenant synthetic retailer.</p>
        <p>{DEMO_SNAPSHOT_LABEL}</p>
        <div style={{ marginTop: 16 }}>
          <ProvenancePill />
        </div>
        <h2 className="card-title" style={{ marginTop: 24 }}>
          API
        </h2>
        <p>
          Configure <code>VITE_API_URL</code> (default proxied to <code>http://127.0.0.1:8000</code>).
        </p>
        <h2 className="card-title" style={{ marginTop: 24 }}>
          Exclusions
        </h2>
        <p style={{ fontSize: 13, color: "var(--color-text-muted)" }}>
          No payments, external supplier APIs, multi-tenant auth, email, cloud deploy, or conversational AI.
          Recommendations are template strings from ML + optimizer outputs.
        </p>
      </section>
    </>
  );
}
