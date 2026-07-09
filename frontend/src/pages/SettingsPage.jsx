import { useState, useEffect } from "react";
import { Key, Bot, User2, Shield, Check, Terminal, RefreshCw, AlertCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { getAiSettings } from "../api/settings";
import { Card, CardHeader } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { Button } from "../components/ui/Button";
import { useAuth } from "../contexts/AuthContext";
import { authApi } from "../api/auth";
import toast from "react-hot-toast";

const AI_PROVIDERS = [
  {
    id: "ollama",
    name: "Ollama",
    model: "llama3.2",
    base_url: "http://localhost:11434/v1",
    api_key: "ollama",
    noteKey: "settings.ai.ollamaNote",
    gradient: "from-violet-500/15 to-purple-500/10",
    border: "border-violet-500/20",
    dot: "bg-violet-400",
  },
  {
    id: "openai",
    name: "OpenAI",
    model: "gpt-4o-mini",
    base_url: "",
    api_key: "sk-...",
    gradient: "from-emerald-500/15 to-teal-500/10",
    border: "border-emerald-500/20",
    dot: "bg-emerald-400",
  },
  {
    id: "gemini",
    name: "Google Gemini",
    model: "gemini-1.5-flash",
    base_url: "",
    api_key: "AIza...",
    gradient: "from-blue-500/15 to-cyan-500/10",
    border: "border-blue-500/20",
    dot: "bg-blue-400",
  },
];

function ProviderCard({ provider, selected, onSelect }) {
  const { t } = useTranslation();
  return (
    <button
      type="button"
      onClick={() => onSelect(provider.id)}
      className={`relative flex flex-col gap-2.5 p-4 rounded-2xl border text-left transition-all duration-200
        ${selected
          ? `bg-gradient-to-br ${provider.gradient} ${provider.border} shadow-lg`
          : "border-white/6 bg-white/[0.02] hover:border-white/12 hover:bg-white/3"
        }`}
    >
      {selected && (
        <div className="absolute top-3 right-3 w-5 h-5 rounded-full bg-violet-600 flex items-center justify-center shadow-md shadow-violet-500/40">
          <Check size={11} className="text-white" strokeWidth={3} />
        </div>
      )}
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${provider.dot}`} />
        <p className={`text-sm font-semibold ${selected ? "text-zinc-100" : "text-zinc-400"}`}>{provider.name}</p>
      </div>
      <p className="text-[11px] font-mono text-zinc-600">{provider.model}</p>
      {provider.noteKey && (
        <p className="text-[10px] text-violet-400/70">{t(provider.noteKey)}</p>
      )}
    </button>
  );
}

export default function SettingsPage() {
  const { user, fetchMe } = useAuth();
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState("account");
  const [selectedProvider, setSelectedProvider] = useState("openai");

  useEffect(() => {
    getAiSettings().then(({ data }) => setSelectedProvider(data.provider)).catch(() => {});
  }, []);

  const TABS = [
    { id: "account",  icon: User2,  label: t("settings.tabs.account") },
    { id: "security", icon: Shield, label: t("settings.tabs.security") },
    { id: "ai",       icon: Bot,    label: t("settings.tabs.ai") },
  ];

  const [accountForm, setAccountForm] = useState({ username: user?.username ?? "" });
  const [accountLoading, setAccountLoading] = useState(false);

  const [pwForm, setPwForm] = useState({ current_password: "", new_password: "", confirm: "" });
  const [pwLoading, setPwLoading] = useState(false);
  const [pwError, setPwError] = useState("");

  async function saveAccount(e) {
    e.preventDefault();
    setAccountLoading(true);
    try {
      const payload = {};
      if (accountForm.username !== user?.username) payload.username = accountForm.username;
      if (!Object.keys(payload).length) { toast(t("settings.account.noChanges")); return; }
      await authApi.updateMe(payload);
      await fetchMe();
      toast.success(t("settings.account.saved"));
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? t("common.error"));
    } finally {
      setAccountLoading(false);
    }
  }

  async function changePassword(e) {
    e.preventDefault();
    setPwError("");
    if (pwForm.new_password !== pwForm.confirm) {
      setPwError(t("settings.security.mismatch")); return;
    }
    if (pwForm.new_password.length < 8) {
      setPwError(t("settings.security.tooShort")); return;
    }
    setPwLoading(true);
    try {
      await authApi.changePassword(pwForm.current_password, pwForm.new_password);
      setPwForm({ current_password: "", new_password: "", confirm: "" });
      toast.success(t("settings.security.changed"));
    } catch (err) {
      setPwError(err?.response?.data?.detail ?? t("common.error"));
    } finally {
      setPwLoading(false);
    }
  }

  const currentProvider = AI_PROVIDERS.find(p => p.id === selectedProvider);

  return (
    <div className="flex flex-col gap-6 max-w-2xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">{t("settings.title")}</h1>
        <p className="text-zinc-500 mt-1 text-sm">{t("settings.subtitle")}</p>
      </div>

      <div className="tab-bar">
        {TABS.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`tab-item flex items-center gap-2 ${activeTab === id ? "active" : ""}`}
          >
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      {activeTab === "account" && (
        <Card className="fade-in">
          <CardHeader
            title={t("settings.account.title")}
            subtitle={t("settings.account.subtitle")}
          />
          <div className="flex items-center gap-4 p-4 rounded-xl bg-white/3 border border-white/6 mb-5">
            <div className="w-12 h-12 rounded-full bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center text-lg font-bold text-white shadow-md shadow-violet-600/20">
              {user?.username?.[0]?.toUpperCase()}
            </div>
            <div>
              <p className="font-semibold text-zinc-200 text-sm">{user?.username}</p>
              <span className="admin-badge mt-1 inline-flex">
                <Shield size={7} /> Admin
              </span>
            </div>
          </div>
          <form onSubmit={saveAccount} className="flex flex-col gap-4">
            <Input
              label={t("settings.account.usernameLabel")}
              icon={User2}
              value={accountForm.username}
              onChange={e => setAccountForm(f => ({ ...f, username: e.target.value }))}
              hint={t("settings.account.usernameHint")}
            />
            <Button type="submit" loading={accountLoading} size="md" className="self-start">
              <RefreshCw size={14} /> {t("common.save")}
            </Button>
          </form>
        </Card>
      )}

      {activeTab === "security" && (
        <Card className="fade-in">
          <CardHeader title={t("settings.security.title")} subtitle={t("settings.security.subtitle")} />
          <form onSubmit={changePassword} className="flex flex-col gap-4">
            <Input
              label={t("settings.security.currentPw")}
              type="password"
              placeholder="••••••••"
              icon={Shield}
              value={pwForm.current_password}
              onChange={e => setPwForm(f => ({ ...f, current_password: e.target.value }))}
              autoComplete="current-password"
              required
            />
            <Input
              label={t("settings.security.newPw")}
              type="password"
              placeholder={t("settings.security.minChars")}
              icon={Key}
              value={pwForm.new_password}
              onChange={e => setPwForm(f => ({ ...f, new_password: e.target.value }))}
              autoComplete="new-password"
              required
            />
            <Input
              label={t("settings.security.confirmPw")}
              type="password"
              placeholder="••••••••"
              icon={Key}
              value={pwForm.confirm}
              onChange={e => setPwForm(f => ({ ...f, confirm: e.target.value }))}
              autoComplete="new-password"
              required
            />
            {pwError && (
              <div className="flex items-start gap-2.5 rounded-xl bg-red-500/8 border border-red-500/18 px-4 py-3 text-sm text-red-400">
                <AlertCircle size={15} className="shrink-0 mt-0.5" /> {pwError}
              </div>
            )}
            <Button type="submit" loading={pwLoading} size="md" className="self-start">
              <Shield size={14} /> {t("settings.security.changePw")}
            </Button>
          </form>
        </Card>
      )}

      {activeTab === "ai" && (
        <div className="flex flex-col gap-4 fade-in">
          <Card>
            <CardHeader
              title={t("settings.ai.title")}
              subtitle={t("settings.ai.subtitle")}
            />
            <div className="grid grid-cols-3 gap-3 mb-5">
              {AI_PROVIDERS.map(p => (
                <ProviderCard
                  key={p.id}
                  provider={p}
                  selected={selectedProvider === p.id}
                  onSelect={setSelectedProvider}
                />
              ))}
            </div>

            <div>
              <div className="flex items-center gap-2 mb-2">
                <Terminal size={13} className="text-zinc-600" />
                <p className="text-xs text-zinc-600 font-medium">backend/.env</p>
              </div>
              <div className="rounded-xl bg-[#0a0a14] border border-white/6 p-4 font-mono text-[12px] leading-relaxed">
                <div className="text-zinc-600 mb-2"># backend/.env</div>
                {[
                  ["AI_PROVIDER", currentProvider?.id],
                  ["AI_MODEL",    currentProvider?.model],
                  ["AI_API_KEY",  currentProvider?.api_key],
                  ["AI_BASE_URL", currentProvider?.base_url],
                ].map(([k, v]) => (
                  <div key={k}>
                    <span className="text-violet-400">{k}</span>
                    <span className="text-zinc-600">=</span>
                    <span className="text-emerald-400">{v || '""'}</span>
                  </div>
                ))}
                <div className="text-zinc-700 mt-3">
                  # {t("settings.ai.restartHint")}
                </div>
              </div>
            </div>
          </Card>

          <div className="flex items-start gap-2.5 rounded-xl bg-amber-500/5 border border-amber-500/15 px-4 py-3">
            <AlertCircle size={14} className="text-amber-500/70 mt-0.5 shrink-0" />
            <p className="text-[12px] text-zinc-600 leading-relaxed">
              {t("settings.ai.note")}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
