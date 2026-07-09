import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, Settings, CheckCheck, Film, AlertCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNotifications } from "../../hooks/useNotifications";
import { Spinner } from "../ui/Spinner";

const LANGS = [
  { code: "uz", label: "UZ" },
  { code: "ru", label: "RU" },
  { code: "en", label: "EN" },
];

function LanguageSwitcher() {
  const { i18n } = useTranslation();
  function changeLang(code) {
    i18n.changeLanguage(code);
    localStorage.setItem("lang", code);
  }
  return (
    <div className="flex items-center gap-0.5 p-0.5 rounded-lg bg-white/[0.04] border border-white/[0.07]">
      {LANGS.map(({ code, label }) => (
        <button
          key={code}
          onClick={() => changeLang(code)}
          className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition-all
            ${i18n.language === code
              ? "bg-violet-600 text-white shadow-sm"
              : "text-zinc-500 hover:text-zinc-300"
            }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function NotificationItem({ notif, onRead, onNavigate }) {
  const { t } = useTranslation();
  const completed = notif.type === "job_completed";

  function handleClick() {
    if (!notif.is_read) onRead(notif.id);
    if (notif.video_id) onNavigate(`/job/${notif.video_id}`);
  }

  return (
    <button
      onClick={handleClick}
      className={`w-full flex items-start gap-3 px-4 py-3 text-left transition-colors
        hover:bg-white/[0.04]
        ${!notif.is_read ? "bg-violet-500/[0.04]" : ""}`}
    >
      <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5
        ${completed ? "bg-emerald-500/15 text-emerald-400" : "bg-red-500/15 text-red-400"}`}>
        {completed ? <Film size={13} /> : <AlertCircle size={13} />}
      </div>
      <div className="flex-1 min-w-0">
        <p className={`text-xs font-semibold leading-snug ${completed ? "text-zinc-100" : "text-red-400"}`}>
          {completed
            ? t("notifications.completed", { count: notif.shorts_count })
            : t("notifications.failed")}
        </p>
        <p className="text-[11px] text-zinc-600 truncate mt-0.5">{notif.title}</p>
        <p className="text-[10px] text-zinc-700 mt-1">{timeAgoShort(notif.created_at)}</p>
      </div>
      {!notif.is_read && (
        <div className="w-1.5 h-1.5 rounded-full bg-violet-400 shrink-0 mt-1.5" />
      )}
    </button>
  );
}

function timeAgoShort(iso) {
  const diff = (Date.now() - new Date(iso)) / 1000;
  if (diff < 60)   return `${Math.floor(diff)}s`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  if (diff < 86400)return `${Math.floor(diff / 3600)}h`;
  return `${Math.floor(diff / 86400)}d`;
}

export function Header() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { items, unreadCount, loading, read, readAll } = useNotifications();
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    function handleClick(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <header className="h-12 shrink-0 flex items-center justify-end gap-3 px-6 border-b border-white/[0.05] bg-[#060610]/60 backdrop-blur-sm sticky top-0 z-30">
      <LanguageSwitcher />

      <button
        onClick={() => navigate("/settings")}
        title={t("nav.settings")}
        className="w-8 h-8 rounded-lg flex items-center justify-center text-zinc-600 hover:text-zinc-300 hover:bg-white/[0.06] transition-all"
      >
        <Settings size={16} strokeWidth={1.8} />
      </button>

      <div ref={dropdownRef} className="relative">
        <button
          onClick={() => setOpen(v => !v)}
          className={`relative w-8 h-8 rounded-lg flex items-center justify-center transition-all
            ${open
              ? "bg-violet-500/15 text-violet-400"
              : "text-zinc-600 hover:text-zinc-300 hover:bg-white/[0.06]"
            }`}
        >
          <Bell size={16} strokeWidth={1.8} />
          {unreadCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full
              bg-violet-600 text-white text-[9px] font-bold flex items-center justify-center
              shadow-sm shadow-violet-600/50">
              {unreadCount > 99 ? "99+" : unreadCount}
            </span>
          )}
        </button>

        {open && (
          <div className="absolute right-0 top-10 w-80 rounded-2xl border border-white/[0.08]
            bg-[#0d0d1f] shadow-2xl shadow-black/60 overflow-hidden z-50">

            <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
              <div className="flex items-center gap-2">
                <p className="text-sm font-semibold text-zinc-200">{t("notifications.title")}</p>
                {unreadCount > 0 && (
                  <span className="px-1.5 py-0.5 rounded-full bg-violet-500/20 text-violet-400 text-[10px] font-bold">
                    {unreadCount}
                  </span>
                )}
              </div>
              {unreadCount > 0 && (
                <button
                  onClick={readAll}
                  className="flex items-center gap-1 text-[11px] text-violet-400 hover:text-violet-300 transition-colors"
                >
                  <CheckCheck size={12} />
                  {t("notifications.readAll")}
                </button>
              )}
            </div>

            <div className="overflow-y-auto max-h-80 divide-y divide-white/[0.04]">
              {loading && items.length === 0 ? (
                <div className="flex items-center justify-center gap-2 py-8 text-zinc-700">
                  <Spinner size={14} /> <span className="text-xs">{t("common.loading")}</span>
                </div>
              ) : items.length === 0 ? (
                <div className="flex flex-col items-center gap-2 py-10 text-center px-4">
                  <Bell size={22} className="text-zinc-800" />
                  <p className="text-xs text-zinc-600">{t("notifications.empty")}</p>
                </div>
              ) : (
                items.map(n => (
                  <NotificationItem
                    key={n.id}
                    notif={n}
                    onRead={read}
                    onNavigate={(path) => { navigate(path); setOpen(false); }}
                  />
                ))
              )}
            </div>

            {items.length > 0 && (
              <div className="px-4 py-2.5 border-t border-white/[0.06]">
                <p className="text-[10px] text-zinc-700 text-center">
                  {t("notifications.hint")}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
