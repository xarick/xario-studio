import { useState } from "react";
import { NavLink, useNavigate, useLocation } from "react-router-dom";
import {
  LayoutDashboard, Film, History, Settings, LogOut, Zap,
  Users, ChevronRight, ImagePlus, Images, Mic, Headphones,
  Wrench, Captions, FileText, Volume2, Mic2, Languages,
  Scissors, Combine,
} from "lucide-react";
import { useAuth } from "../../contexts/AuthContext";
import { useTranslation } from "react-i18next";

/* ── Collapsible nav module ────────────────────────────────────── */
const MODULE_COLORS = {
  violet: {
    icon:   "bg-violet-500/12 text-violet-400 border-violet-500/15",
    open:   "bg-violet-500/8 text-zinc-300",
    hover:  "hover:bg-violet-500/5 hover:text-zinc-300 text-zinc-500",
    line:   "border-violet-500/10",
  },
  amber: {
    icon:   "bg-amber-500/12 text-amber-400 border-amber-500/15",
    open:   "bg-amber-500/8 text-zinc-300",
    hover:  "hover:bg-amber-500/5 hover:text-zinc-300 text-zinc-500",
    line:   "border-amber-500/10",
  },
  rose: {
    icon:   "bg-rose-500/12 text-rose-400 border-rose-500/15",
    open:   "bg-rose-500/8 text-zinc-300",
    hover:  "hover:bg-rose-500/5 hover:text-zinc-300 text-zinc-500",
    line:   "border-rose-500/10",
  },
};

function NavModule({ id, icon: Icon, label, color = "violet", links, defaultOpen = false }) {
  const [open, setOpen] = useState(() => {
    const stored = localStorage.getItem(`nav_${id}`);
    return stored !== null ? stored === "true" : defaultOpen;
  });

  const c = MODULE_COLORS[color] ?? MODULE_COLORS.violet;

  function toggle() {
    const next = !open;
    setOpen(next);
    localStorage.setItem(`nav_${id}`, String(next));
  }

  return (
    <div>
      <button
        onClick={toggle}
        className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-xl border border-transparent
          transition-all duration-150 ${open ? c.open : c.hover}`}
      >
        <div className={`w-6 h-6 rounded-lg border flex items-center justify-center shrink-0 ${c.icon}`}>
          <Icon size={13} strokeWidth={2} />
        </div>
        <span className="flex-1 text-left text-[12px] font-semibold uppercase tracking-wide">
          {label}
        </span>
        <ChevronRight
          size={12}
          className={`text-zinc-700 shrink-0 transition-transform duration-200 ${open ? "rotate-90" : ""}`}
        />
      </button>

      <div className={`grid transition-all duration-200 ease-in-out ${open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}>
        <div className="overflow-hidden">
          <div className="pl-[22px] pt-1 pb-0.5">
            <div className={`border-l ${c.line} pl-2.5 flex flex-col gap-0.5`}>
              {links.map(({ to, icon: LIcon, label: lbl }) => (
                <NavLink
                  key={to}
                  to={to}
                  className={({ isActive }) => `nav-link py-[7px] text-[13px] ${isActive ? "active" : ""}`}
                >
                  <LIcon size={13} strokeWidth={1.8} />
                  <span>{lbl}</span>
                </NavLink>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Sidebar ───────────────────────────────────────────────────── */
export function Sidebar() {
  const { user, logout } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const isSuperAdmin = user?.role === "superadmin";

  const initials = user?.username?.[0]?.toUpperCase() ?? "A";

  const isVideoPath = location.pathname.startsWith("/video")
    || location.pathname.startsWith("/job/");
  const isAudioPath = location.pathname.startsWith("/audio");
  const isPhotoPath = location.pathname.startsWith("/image");

  return (
    <aside className="w-56 shrink-0 flex flex-col h-screen sticky top-0 glass-panel border-r border-white/[0.05]">

      {/* Logo */}
      <div className="px-4 pt-5 pb-4 shrink-0">
        <div className="flex items-center gap-2.5 px-2">
          <div className="relative w-8 h-8">
            <div className="absolute inset-0 rounded-lg bg-gradient-to-br from-violet-600 to-indigo-600 shadow-lg shadow-violet-600/30" />
            <div className="relative w-full h-full flex items-center justify-center">
              <Zap size={15} className="text-white" strokeWidth={2.5} />
            </div>
          </div>
          <div className="flex items-baseline gap-1 leading-none">
            <span className="font-bold text-sm tracking-tight text-zinc-100">xario</span>
            <span className="font-bold text-sm tracking-tight gradient-text">studio</span>
          </div>
        </div>
      </div>

      <div className="mx-4 h-px bg-white/[0.05] shrink-0" />

      {/* Scrollable nav */}
      <nav className="flex-1 px-3 py-3 flex flex-col gap-0.5 overflow-y-auto">

        {/* Dashboard */}
        <NavLink
          to="/dashboard"
          className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
        >
          <LayoutDashboard size={15} strokeWidth={1.8} />
          <span>{t("nav.dashboard")}</span>
        </NavLink>

        <div className="h-px bg-white/[0.04] my-2" />

        {/* Video */}
        <NavModule
          id="video"
          icon={Film}
          label={t("nav.videos")}
          color="violet"
          defaultOpen={isVideoPath}
          links={[
            { to: "/video/new",      icon: Film,      label: t("nav.newVideo") },
            { to: "/video/editor",   icon: Scissors,  label: t("nav.editor") },
            { to: "/video/merge",    icon: Combine,   label: t("nav.videoMerge") },
            { to: "/video/subtitle", icon: Captions,  label: t("nav.subtitle") },
            { to: "/video/transcribe", icon: FileText, label: t("nav.videoToText") },
            { to: "/video/cleanup",  icon: Volume2,   label: t("nav.cleanup") },
            { to: "/video/separate", icon: Mic2,      label: t("nav.separate") },
            { to: "/video/dub",      icon: Languages, label: t("nav.dub") },
            { to: "/video/history",  icon: History,   label: t("nav.history") },
          ]}
        />

        {/* Audio */}
        <NavModule
          id="audio"
          icon={Mic}
          label={t("nav.audios")}
          color="amber"
          defaultOpen={isAudioPath}
          links={[
            { to: "/audio/new",        icon: Mic,        label: t("nav.newAudio") },
            { to: "/audio/transcribe", icon: FileText,   label: t("nav.transcribe") },
            { to: "/audio/cleanup",    icon: Volume2,    label: t("nav.cleanup") },
            { to: "/audio/separate",   icon: Mic2,       label: t("nav.separate") },
            { to: "/audio/dub",        icon: Languages,  label: t("nav.dub") },
            { to: "/audio/history",    icon: Headphones, label: t("nav.audioHistory") },
          ]}
        />

        {/* Image */}
        <NavModule
          id="image"
          icon={ImagePlus}
          label={t("nav.photos")}
          color="rose"
          defaultOpen={isPhotoPath}
          links={[
            { to: "/image/new",           icon: ImagePlus, label: t("nav.newPhoto") },
            { to: "/image/to-shorts",     icon: Film,      label: t("nav.img2Short") },
            { to: "/image/history",       icon: Images,    label: t("nav.photoHistory") },
          ]}
        />

        <div className="h-px bg-white/[0.04] my-2" />

        {/* Tools — single page */}
        <NavLink
          to="/tools"
          className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
        >
          <Wrench size={15} strokeWidth={1.8} />
          <span>{t("nav.tools")}</span>
        </NavLink>

        <div className="h-px bg-white/[0.04] my-2" />

        {/* System */}
        <p className="section-label mb-0.5">{t("nav.system")}</p>
        {[
          ...(isSuperAdmin ? [{ to: "/users",    icon: Users,    label: t("nav.users") }] : []),
          {                   to: "/settings",   icon: Settings, label: t("nav.settings") },
        ].map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
          >
            <Icon size={15} strokeWidth={1.8} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* User card + footer */}
      <div className="px-3 pb-3 shrink-0">
        <div className="flex items-center gap-2.5 px-2 py-2 rounded-xl hover:bg-white/3 transition-colors group">
          <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0
            bg-gradient-to-br from-violet-600 to-indigo-600 shadow-md shadow-violet-600/20">
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-zinc-200 truncate">{user?.username}</p>
          </div>
          <button
            onClick={() => { logout(); navigate("/login"); }}
            title={t("common.logout")}
            className="opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-lg text-zinc-600 hover:text-red-400 hover:bg-red-500/10"
          >
            <LogOut size={14} />
          </button>
        </div>

        <div className="mt-2 pt-2.5 border-t border-white/[0.04] flex flex-col items-center gap-1">
          <p className="text-[11px] text-zinc-500 leading-none">
            Developed by{" "}
            <span className="text-violet-400/80 font-semibold">itone.uz</span>
          </p>
          <p className="text-[10px] text-zinc-700 leading-none font-medium">v1.0.0</p>
        </div>
      </div>
    </aside>
  );
}
