import { ProvenancePill } from "../components/ProvenancePill";
import { PageHeader } from "../components/Controls";
import { DEMO_SNAPSHOT_LABEL } from "../utils/dates";

export function Settings() {
  return (
    <>
      <PageHeader title="Settings" subtitle="Read-only demo configuration for Summit Retail Co." />
      <div className="agents-layout">
        <section className="card">
          <h2 className="card-title">Demo identity</h2>
          <p>Single synthetic retailer. There is no account system and no external supplier connection.</p>
          <p>{DEMO_SNAPSHOT_LABEL}</p>
          <ProvenancePill />
          <h2 className="card-title" style={{ marginTop: 22 }}>API</h2>
          <p>
            The UI calls <code>/api</code>. In development, Vite proxies that to <code>http://127.0.0.1:8000</code>. Set{" "}
            <code>VITE_API_URL</code> only if the API is elsewhere.
          </p>
        </section>
        <section className="card">
          <h2 className="card-title">What this demo does not do</h2>
          <ul>
            <li>No payments or purchase orders sent to suppliers.</li>
            <li>No multi-tenant login, email, or cloud requirement.</li>
            <li>No language model. Recommendation text is filled from model and optimizer fields.</li>
            <li>Approving a reorder does not change on-hand stock. Receiving does, once.</li>
          </ul>
        </section>
      </div>
    </>
  );
}
