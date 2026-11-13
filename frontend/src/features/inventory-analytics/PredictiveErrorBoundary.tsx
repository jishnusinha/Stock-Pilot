import { Component, type ReactNode } from "react";

type Props = { children: ReactNode; label?: string };
type State = { error: string | null };

/** Keeps the analytics shell alive if a chart throws during render. */
export class PredictiveErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error: error?.message || "Render failed" };
  }

  render() {
    if (this.state.error) {
      return (
        <section className="card" role="alert">
          <h2 className="card-title">{this.props.label ?? "Predictive panel"}</h2>
          <p className="note">This panel failed to render: {this.state.error}</p>
          <button type="button" className="btn btn-secondary" onClick={() => this.setState({ error: null })}>
            Retry panel
          </button>
        </section>
      );
    }
    return this.props.children;
  }
}
