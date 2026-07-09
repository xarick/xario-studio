export function Card({ children, className = "", hover = false, gradient = false }) {
  return (
    <div
      className={`glass p-6
        ${hover ? "glass-hover cursor-pointer" : ""}
        ${gradient ? "gradient-border" : ""}
        ${className}`}
    >
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, action }) {
  return (
    <div className="flex items-start justify-between mb-6">
      <div>
        <h3 className="text-base font-semibold text-zinc-100">{title}</h3>
        {subtitle && <p className="text-sm text-zinc-500 mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
