import { useNavigate } from "react-router-dom";
import {
  Film, Scissors, CheckCircle2, Loader2, Plus, ArrowRight, AlertCircle,
  Captions, Mic, ImagePlus, Wrench,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Spinner } from "../components/ui/Spinner";
import { useVideos } from "../hooks/useVideos";
import { useAuth } from "../contexts/AuthContext";
import { useDashboardStats } from "../hooks/useDashboardStats";
import { formatDuration, timeAgo } from "../utils/format";

function StatCard({ icon: Icon, value, label, color, loading }) {
  const colorMap = {
    violet:  { bg: "from-violet-500/10 to-transparent",  icon: "bg-violet-500/15 text-violet-400",  glow: "hover:shadow-violet-500/10" },
    indigo:  { bg: "from-indigo-500/10 to-transparent",  icon: "bg-indigo-500/15 text-indigo-400",  glow: "hover:shadow-indigo-500/10" },
    emerald: { bg: "from-emerald-500/10 to-transparent", icon: "bg-emerald-500/15 text-emerald-400",glow: "hover:shadow-emerald-500/10" },
    amber:   { bg: "from-amber-500/10 to-transparent",   icon: "bg-amber-500/15 text-amber-400",    glow: "hover:shadow-amber-500/10" },
  };
  const c = colorMap[color] ?? colorMap.violet;
  return (
    <div className={`glass relative overflow-hidden group p-5 transition-all duration-300 hover:shadow-xl ${c.glow}`}>
      <div className={`absolute inset-0 bg-gradient-to-br ${c.bg} opacity-50`} />
      <div className="relative">
        <div className={`w-9 h-9 rounded-xl flex items-center justify-center mb-4 ${c.icon}`}>
          <Icon size={18} strokeWidth={1.8} />
        </div>
        {loading ? (
          <div className="h-8 w-16 shimmer rounded-lg mb-1" />
        ) : (
          <div className="stat-value mb-1">{value}</div>
        )}
        <p className="text-[13px] text-zinc-500">{label}</p>
      </div>
    </div>
  );
}

const QUICK_ACTIONS = [
  { to: "/video/new",           icon: Film,     labelKey: "nav.newVideo",   color: "violet" },
  { to: "/video/editor",        icon: Scissors, labelKey: "nav.editor",     color: "violet" },
  { to: "/video/subtitle",      icon: Captions, labelKey: "nav.subtitle",   color: "violet" },
  { to: "/audio/new",           icon: Mic,      labelKey: "nav.newAudio",   color: "amber" },
  { to: "/image/new",           icon: ImagePlus, labelKey: "nav.newPhoto",  color: "rose" },
  { to: "/tools",               icon: Wrench,   labelKey: "nav.tools",      color: "cyan" },
];

const QA_COLORS = {
  violet: "bg-violet-500/10 border-violet-500/20 text-violet-400",
  amber:  "bg-amber-500/10 border-amber-500/20 text-amber-400",
  rose:   "bg-rose-500/10 border-rose-500/20 text-rose-400",
  cyan:   "bg-cyan-500/10 border-cyan-500/20 text-cyan-400",
};

function QuickActions() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  return (
    <div>
      <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-widest mb-4">
        {t("dashboard.quickActions")}
      </h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {QUICK_ACTIONS.map(({ to, icon: Icon, labelKey, color }) => (
          <button
            key={to}
            onClick={() => navigate(to)}
            className="group flex flex-col items-center gap-2.5 p-4 rounded-2xl border border-white/[0.06]
              bg-white/[0.02] hover:border-white/15 hover:bg-white/[0.04] hover:-translate-y-0.5 transition-all duration-200"
          >
            <div className={`w-10 h-10 rounded-xl border flex items-center justify-center ${QA_COLORS[color]}`}>
              <Icon size={18} strokeWidth={1.8} />
            </div>
            <span className="text-[12px] font-medium text-zinc-400 group-hover:text-zinc-200 text-center leading-tight transition-colors">
              {t(labelKey)}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function EmptyState({ onNew }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col items-center gap-5 py-16 text-center">
      <div className="relative">
        <div className="w-20 h-20 rounded-3xl bg-violet-500/8 border border-violet-500/15 flex items-center justify-center">
          <Film size={32} className="text-violet-400/60" />
        </div>
        <div className="absolute -bottom-1 -right-1 w-7 h-7 rounded-full bg-violet-600 border-2 border-[#060610] flex items-center justify-center">
          <Plus size={14} className="text-white" strokeWidth={3} />
        </div>
      </div>
      <div>
        <p className="font-semibold text-zinc-200 mb-1">{t("dashboard.empty.title")}</p>
        <p className="text-sm text-zinc-600 max-w-xs">{t("dashboard.empty.subtitle")}</p>
      </div>
      <Button onClick={onNew} size="sm">
        <Plus size={14} /> {t("dashboard.empty.action")}
      </Button>
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data, loading: videosLoading } = useVideos();
  const { stats, loading: statsLoading } = useDashboardStats();

  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-zinc-600 uppercase tracking-widest mb-1.5">Admin Panel</p>
          <h1 className="text-2xl font-bold tracking-tight">
            <span className="text-zinc-100">{t("dashboard.greeting")} </span>
            <span className="gradient-text">{user?.username}</span>
          </h1>
          <p className="text-zinc-500 mt-1 text-sm">{t("dashboard.subtitle")}</p>
        </div>
        <Button onClick={() => navigate("/video/new")}>
          <Plus size={15} /> {t("dashboard.newVideo")}
        </Button>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard icon={Film}         value={stats.total_videos}  label={t("dashboard.stats.totalVideos")}  color="violet"  loading={statsLoading} />
        <StatCard icon={Scissors}     value={stats.total_shorts}  label={t("dashboard.stats.shortsCreated")} color="indigo"  loading={statsLoading} />
        <StatCard icon={CheckCircle2} value={stats.completed}     label={t("dashboard.stats.successful")}   color="emerald" loading={statsLoading} />
        <StatCard icon={Loader2}      value={stats.processing}    label={t("dashboard.stats.processing")}   color="amber"   loading={statsLoading} />
      </div>

      <QuickActions />

      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-widest">
            {t("dashboard.recentVideos")}
          </h2>
          <button
            onClick={() => navigate("/video/history")}
            className="flex items-center gap-1 text-[13px] text-violet-400 hover:text-violet-300 transition-colors"
          >
            {t("dashboard.viewAll")} <ArrowRight size={13} />
          </button>
        </div>

        {videosLoading ? (
          <div className="flex flex-col gap-2">
            {[1,2,3].map(i => <div key={i} className="glass h-16 shimmer" />)}
          </div>
        ) : data.items.length === 0 ? (
          <Card>
            <EmptyState onNew={() => navigate("/video/new")} />
          </Card>
        ) : (
          <div className="flex flex-col gap-2">
            {data.items.slice(0, 8).map(v => (
              <div
                key={v.id}
                onClick={() => navigate(`/job/${v.id}`)}
                className="table-row cursor-pointer group"
                style={{ gridTemplateColumns: "1fr auto auto" }}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className={`w-2 h-2 rounded-full shrink-0 ${
                    v.status === "completed" ? "bg-emerald-400" :
                    v.status === "failed"    ? "bg-red-400" :
                    v.status === "pending"   ? "bg-zinc-600" :
                    "bg-amber-400 status-dot-pulse"
                  }`} />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-zinc-200 truncate leading-snug">
                      {v.original_filename ?? v.source_url ?? "Video"}
                    </p>
                    <p className="text-[11px] text-zinc-600 mt-0.5">
                      {v.shorts_requested} short
                      {v.duration_seconds ? ` · ${formatDuration(v.duration_seconds)}` : ""}
                      {" · "}{timeAgo(v.created_at)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {v.status === "processing" && (
                    <span className="text-[11px] text-amber-400 tabular-nums">{v.progress_percent}%</span>
                  )}
                  <Badge status={v.status} />
                </div>
                <ArrowRight size={14} className="text-zinc-700 group-hover:text-zinc-400 transition-colors ml-2" />
              </div>
            ))}
          </div>
        )}
      </div>

      {stats.failed > 0 && !statsLoading && (
        <div className="flex items-start gap-3 p-4 rounded-xl bg-red-500/5 border border-red-500/15">
          <AlertCircle size={16} className="text-red-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-red-400">
              {t("dashboard.failedAlert_other", { count: stats.failed })}
            </p>
            <button
              onClick={() => navigate("/video/history")}
              className="text-xs text-red-400/60 hover:text-red-400 transition-colors mt-0.5"
            >
              {t("dashboard.viewHistory")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
