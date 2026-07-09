import { useTranslation } from "react-i18next";
import { Select } from "./ui/Select";

/** Renders a tool's parameter fields from its config (range / number / select). */
export function ToolFields({ fields, values, onChange }) {
  const { t } = useTranslation();
  if (!fields.length) return null;

  return (
    <div className="flex flex-col gap-4">
      {fields.map(f => {
        const val = values[f.key];
        const label = t(f.label);

        if (f.type === "select") {
          const options = f.options.map(o => ({ value: o.value, label: o.i18n ? t(o.label) : o.label }));
          return (
            <div key={f.key} className="flex items-center justify-between gap-4">
              <label className="text-sm font-medium text-zinc-300">{label}</label>
              <Select value={val} onChange={v => onChange(f.key, v)} options={options} className="w-40" />
            </div>
          );
        }

        if (f.type === "range") {
          return (
            <div key={f.key} className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-zinc-300">{label}</label>
                <span className="text-sm tabular-nums text-violet-300">{val}{f.unit ? ` ${f.unit}` : ""}</span>
              </div>
              <input type="range" min={f.min} max={f.max} step={f.step} value={val}
                onChange={e => onChange(f.key, Number(e.target.value))}
                className="w-full accent-violet-500 cursor-pointer" />
            </div>
          );
        }

        // number
        return (
          <div key={f.key} className="flex items-center justify-between gap-4">
            <label className="text-sm font-medium text-zinc-300">{label}</label>
            <div className="flex items-center gap-2">
              <input type="number" min={f.min} max={f.max} step={f.step} value={val}
                onChange={e => onChange(f.key, Number(e.target.value))}
                className="w-24 rounded-lg bg-white/[0.04] border border-white/10 px-3 py-1.5 text-sm text-zinc-200
                  focus:outline-none focus:border-violet-500/50" />
              {f.unit && <span className="text-xs text-zinc-500">{f.unit}</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
