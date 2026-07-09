import { useState, useRef, useEffect, useCallback } from "react";
import { Check, ChevronDown } from "lucide-react";

/**
 * Custom dropdown that matches the design system (the native <select> can't be
 * styled to fit the dark glass UI). Closes on outside-click / Escape and is
 * keyboard reachable.
 *
 *   <Select value={lang} onChange={setLang} options={[{ value, label, hint? }]} />
 */
export function Select({
  value,
  onChange,
  options = [],
  placeholder = "—",
  icon: Icon,
  className = "",
  align = "right",
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e) {
      if (ref.current && !ref.current.contains(e.target)) close();
    }
    function onKey(e) {
      if (e.key === "Escape") close();
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, close]);

  const selected = options.find(o => o.value === value);

  return (
    <div ref={ref} className={`relative ${className}`}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className={`group flex items-center gap-2 w-full justify-between rounded-lg
          bg-white/[0.04] border px-3 py-2 text-sm text-zinc-200 transition-colors
          focus:outline-none
          ${open ? "border-violet-500/50 bg-white/[0.06]" : "border-white/10 hover:border-white/20"}`}
      >
        <span className="flex items-center gap-2 min-w-0">
          {Icon && <Icon size={15} className="text-zinc-500 shrink-0" strokeWidth={1.8} />}
          <span className={`truncate ${selected ? "text-zinc-200" : "text-zinc-500"}`}>
            {selected ? selected.label : placeholder}
          </span>
        </span>
        <ChevronDown
          size={15}
          className={`text-zinc-500 shrink-0 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <ul
          role="listbox"
          className={`absolute z-30 mt-1.5 min-w-full w-max max-w-[16rem] max-h-64 overflow-y-auto
            rounded-xl border border-white/10 bg-[#16162a]/95 backdrop-blur-xl p-1
            shadow-xl shadow-black/40 fade-in
            ${align === "right" ? "right-0" : "left-0"}`}
        >
          {options.map(opt => {
            const active = opt.value === value;
            return (
              <li key={String(opt.value)} role="option" aria-selected={active}>
                <button
                  type="button"
                  onClick={() => { onChange(opt.value); close(); }}
                  className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm transition-colors
                    ${active ? "bg-violet-500/15 text-zinc-100" : "text-zinc-300 hover:bg-white/5"}`}
                >
                  <span className="flex-1 min-w-0">
                    <span className="block truncate">{opt.label}</span>
                    {opt.hint && <span className="block text-[11px] text-zinc-500 truncate">{opt.hint}</span>}
                  </span>
                  {active && <Check size={14} className="text-violet-400 shrink-0" strokeWidth={2.5} />}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
