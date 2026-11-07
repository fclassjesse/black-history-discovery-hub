export function Notice({ kind = "info", children, role }: { kind?: "info" | "error" | "ok" | "warn"; children: React.ReactNode; role?: "alert" | "status" }) {
  const cls = kind === "error" ? "bg-danger-tint text-danger" : kind === "ok" ? "bg-ok-tint text-moss-deep" : kind === "warn" ? "bg-sun-tint text-ink" : "bg-chalk-2 text-ink";
  return (
    <div role={role ?? (kind === "error" ? "alert" : "status")} className={`rounded-2xl px-4 py-3 text-sm ${cls}`}>
      {children}
    </div>
  );
}
