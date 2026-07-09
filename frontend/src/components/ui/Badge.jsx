const config = {
  pending:     { dot: "bg-zinc-500",   text: "text-zinc-400",    bg: "bg-zinc-500/10  border-zinc-500/20",  label: "Kutilmoqda",         pulse: false },
  downloading: { dot: "bg-blue-400",   text: "text-blue-400",    bg: "bg-blue-500/10  border-blue-500/20",  label: "Yuklanmoqda",        pulse: true  },
  processing:  { dot: "bg-amber-400",  text: "text-amber-400",   bg: "bg-amber-500/10 border-amber-500/20", label: "Ishlanmoqda",        pulse: true  },
  completed:   { dot: "bg-emerald-400",text: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/20", label: "Tayyor",         pulse: false },
  failed:      { dot: "bg-red-400",    text: "text-red-400",     bg: "bg-red-500/10   border-red-500/20",   label: "Xato",               pulse: false },
};

export function Badge({ status, label: overrideLabel, className = "" }) {
  const c = config[status] ?? config.pending;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border tracking-wide whitespace-nowrap ${c.bg} ${c.text} ${className}`}>
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${c.dot} ${c.pulse ? "status-dot-pulse" : ""}`} />
      {overrideLabel ?? c.label}
    </span>
  );
}
