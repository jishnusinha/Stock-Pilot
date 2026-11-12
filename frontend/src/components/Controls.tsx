import type { ReactNode } from "react";

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle ? <p className="subtitle">{subtitle}</p> : null}
      </div>
      {actions ? <div className="page-header-meta">{actions}</div> : null}
    </header>
  );
}

export function ProgressBar({
  value,
  tone = "ok",
  label,
}: {
  value: number;
  tone?: "ok" | "warn" | "risk" | "info";
  label?: string;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  const cls = tone === "ok" ? "progress" : `progress ${tone === "warn" ? "warn" : tone}`;
  return (
    <div className={cls} role="meter" aria-valuenow={Math.round(clamped)} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
      <span style={{ width: `${clamped}%` }} />
    </div>
  );
}

export function SegmentedControl<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { id: T; label: string }[];
  onChange: (id: T) => void;
  label: string;
}) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          aria-pressed={value === option.id}
          onClick={() => onChange(option.id)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function SliderControl({
  label,
  value,
  min,
  max,
  step = 1,
  display,
  minLabel,
  maxLabel,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  display: string;
  minLabel?: string;
  maxLabel?: string;
  onChange: (value: number) => void;
}) {
  const id = label.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return (
    <div className="slider-row">
      <header>
        <label htmlFor={id}>{label}</label>
        <span className="tabular">{display}</span>
      </header>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={Number.isFinite(value) ? value : min}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-valuemin={min}
        aria-valuemax={max}
        aria-valuenow={value}
      />
      <div className="slider-ends tabular">
        <span>{minLabel ?? String(min)}</span>
        <span>{maxLabel ?? String(max)}</span>
      </div>
    </div>
  );
}
