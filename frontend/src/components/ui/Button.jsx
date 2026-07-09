import { Loader2 } from "lucide-react";

const variants = {
  primary:   "btn-gradient text-white font-semibold",
  secondary: "bg-white/5 hover:bg-white/10 border border-white/10 hover:border-violet-500/30 text-zinc-200 font-medium transition-all",
  ghost:     "hover:bg-white/5 text-zinc-400 hover:text-zinc-200 transition-all",
  danger:    "bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 hover:border-red-500/40 text-red-400 font-medium transition-all",
  outline:   "border border-violet-500/30 hover:border-violet-500/60 hover:bg-violet-500/5 text-violet-400 font-medium transition-all",
};

const sizes = {
  xs: "px-2.5 py-1.5 text-xs rounded-md gap-1",
  sm: "px-3.5 py-2 text-sm rounded-lg gap-1.5",
  md: "px-5 py-2.5 text-sm rounded-[10px] gap-2",
  lg: "px-7 py-3.5 text-base rounded-xl gap-2",
};

export function Button({
  children,
  variant = "primary",
  size = "md",
  loading = false,
  disabled = false,
  className = "",
  type = "button",
  ...props
}) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center relative z-0 select-none
        ${variants[variant]} ${sizes[size]} ${className}
        disabled:opacity-40 disabled:cursor-not-allowed disabled:pointer-events-none`}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Loader2 size={size === "xs" ? 12 : size === "sm" ? 14 : 16} className="spin shrink-0" />}
      {children}
    </button>
  );
}
