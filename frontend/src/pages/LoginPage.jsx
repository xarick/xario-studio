import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { User, Lock, Zap, Shield } from "lucide-react";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { useAuth } from "../contexts/AuthContext";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";

export default function LoginPage() {
  const { login } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: "", password: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(form.username, form.password);
      toast.success(t("login.welcome"));
      navigate("/dashboard");
    } catch (err) {
      setError(err?.response?.data?.detail ?? t("login.invalidCredentials"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden px-4">
      <div className="orb w-[500px] h-[500px] bg-violet-700/12 -top-32 -left-32" />
      <div className="orb w-80 h-80 bg-indigo-700/10 bottom-0 right-0" style={{ animationDelay: "4s" }} />
      <div className="absolute inset-0 opacity-[0.015]"
        style={{ backgroundImage: "radial-gradient(circle at 1px 1px, #7c3aed 1px, transparent 0)", backgroundSize: "32px 32px" }}
      />

      <div className="w-full max-w-sm relative z-10 slide-up">
        <div className="flex flex-col items-center mb-8">
          <div className="relative mb-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-violet-600 to-indigo-600
              shadow-2xl shadow-violet-600/40 flex items-center justify-center">
              <Zap size={26} className="text-white" strokeWidth={2.5} />
            </div>
            <div className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-emerald-500 border-2 border-[#060610] flex items-center justify-center">
              <Shield size={9} className="text-white" strokeWidth={3} />
            </div>
          </div>
          <h1 className="text-2xl font-bold tracking-tight">
            <span className="text-zinc-100">xario</span><span className="gradient-text">studio</span>
          </h1>
          <p className="text-zinc-600 mt-1 text-sm">{t("login.subtitle")}</p>
        </div>

        <div className="glass p-7">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <Input
              label={t("login.username")}
              type="text"
              placeholder="username"
              icon={User}
              value={form.username}
              onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
              autoComplete="username"
              required
            />
            <Input
              label={t("login.password")}
              type="password"
              placeholder="••••••••"
              icon={Lock}
              value={form.password}
              onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
              autoComplete="current-password"
              required
            />

            {error && (
              <div className="rounded-xl bg-red-500/8 border border-red-500/18 px-4 py-3 text-sm text-red-400">
                {error}
              </div>
            )}

            <Button type="submit" loading={loading} size="lg" className="mt-1">
              {t("login.submit")}
            </Button>
          </form>
        </div>

        <p className="text-center text-[11px] text-zinc-700 mt-5">
          {t("login.footer")}
        </p>
      </div>
    </div>
  );
}
