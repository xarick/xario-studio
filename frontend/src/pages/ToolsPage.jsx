import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Film, Mic, ImagePlus } from "lucide-react";
import { toolsBySection, ACCENTS } from "../config/tools";

const SECTIONS = [
  { id: "video", icon: Film,      color: "violet" },
  { id: "audio", icon: Mic,       color: "amber" },
  { id: "image", icon: ImagePlus, color: "rose" },
];

export default function ToolsPage() {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col gap-10 max-w-4xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">{t("toolHub.title")}</h1>
        <p className="text-zinc-500 mt-1 text-sm">{t("toolHub.subtitle")}</p>
      </div>

      {SECTIONS.map(({ id, icon: SIcon, color }) => {
        const tools = toolsBySection(id);
        const accent = ACCENTS[color];
        return (
          <div key={id} className="flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <div className={`w-6 h-6 rounded-lg ${accent.chip} border ${accent.border} flex items-center justify-center`}>
                <SIcon size={13} className={accent.text} strokeWidth={2} />
              </div>
              <h2 className="text-sm font-semibold text-zinc-300 uppercase tracking-wide">{t(`toolHub.${id}`)}</h2>
            </div>

            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {tools.map(tool => {
                const Icon = tool.icon;
                return (
                  <Link
                    key={tool.id}
                    to={tool.route || `/${id}/tool/${tool.op}`}
                    className="group flex items-start gap-3 p-4 rounded-2xl border border-white/[0.06] bg-white/[0.02]
                      hover:border-white/15 hover:bg-white/[0.04] transition-all duration-150"
                  >
                    <div className={`w-9 h-9 rounded-xl ${accent.bg} border ${accent.border} flex items-center justify-center shrink-0`}>
                      <Icon size={17} className={accent.text} strokeWidth={1.8} />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-zinc-200 group-hover:text-white transition-colors flex items-center gap-1.5">
                        {t(`toolDefs.${tool.id}.name`)}
                        {tool.badge && (
                          <span className="text-[8px] bg-violet-500/15 text-violet-300 px-1.5 py-px rounded font-bold uppercase tracking-wider">
                            {tool.badge}
                          </span>
                        )}
                      </p>
                      <p className="text-[11px] text-zinc-600 mt-0.5 leading-snug">{t(`toolDefs.${tool.id}.desc`)}</p>
                    </div>
                  </Link>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
