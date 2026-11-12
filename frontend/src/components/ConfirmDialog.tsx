import { useEffect, useRef } from "react";

export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  onConfirm,
  onCancel,
  danger,
}: {
  open: boolean;
  title: string;
  children: React.ReactNode;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  danger?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);

  if (!open) return null;

  return (
    <dialog
      ref={ref}
      onCancel={(e) => {
        e.preventDefault();
        onCancel();
      }}
      style={{
        border: "1px solid var(--color-border)",
        borderRadius: 14,
        padding: 24,
        maxWidth: 420,
        boxShadow: "0 8px 32px rgba(0,0,0,0.12)",
      }}
    >
      <h2 style={{ marginTop: 0 }}>{title}</h2>
      <div style={{ marginBottom: 20 }}>{children}</div>
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
        <button type="button" className="btn btn-secondary" onClick={onCancel}>
          Cancel
        </button>
        <button
          type="button"
          className={`btn ${danger ? "btn-primary" : "btn-primary"}`}
          onClick={onConfirm}
          style={danger ? { background: "var(--color-risk)" } : undefined}
        >
          {confirmLabel}
        </button>
      </div>
    </dialog>
  );
}
