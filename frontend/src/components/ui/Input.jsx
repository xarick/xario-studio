export function Input({ label, error, hint, icon: Icon, className = "", ...props }) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label className="text-sm font-medium text-zinc-300">{label}</label>
      )}
      <div className="relative">
        {Icon && (
          <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none">
            <Icon size={16} />
          </div>
        )}
        <input
          className={`w-full bg-white/[0.04] border border-white/10 rounded-[10px]
            px-4 py-2.5 text-sm text-zinc-100 placeholder-zinc-600
            input-glow transition-all duration-200
            ${Icon ? "pl-10" : ""}
            ${error ? "border-red-500/50 focus:border-red-500/70" : ""}
            ${className}`}
          {...props}
        />
      </div>
      {error && <p className="text-xs text-red-400 flex items-center gap-1">{error}</p>}
      {hint && !error && <p className="text-xs text-zinc-600">{hint}</p>}
    </div>
  );
}
