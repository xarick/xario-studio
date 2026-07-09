import { useState, useEffect, useCallback } from "react";
import { UserPlus, Trash2, Shield, User2, RefreshCw, X, Eye, EyeOff } from "lucide-react";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { Card, CardHeader } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Spinner } from "../components/ui/Spinner";
import { listUsers, createUser, updateUser, deleteUser } from "../api/admin";
import { extractApiError, timeAgo } from "../utils/format";

const ROLE_CONFIG = {
  admin: { label: "Admin", dot: "bg-violet-400", text: "text-violet-400", bg: "bg-violet-500/10 border-violet-500/20" },
  user:  { label: "User",  dot: "bg-zinc-400",   text: "text-zinc-400",   bg: "bg-zinc-500/10  border-zinc-500/20"  },
};

function RoleBadge({ role }) {
  const c = ROLE_CONFIG[role] ?? ROLE_CONFIG.user;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border tracking-wide ${c.bg} ${c.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${c.dot}`} />
      {c.label}
    </span>
  );
}

const EMPTY_FORM = { username: "", password: "", role: "admin" };

export default function UsersPage() {
  const { t } = useTranslation();
  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(null);
  const [toggling, setToggling] = useState(null);

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [showPw, setShowPw] = useState(false);
  const [formLoading, setFormLoading] = useState(false);
  const [formError, setFormError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await listUsers(1, 50);
      setUsers(data.items);
      setTotal(data.total);
    } catch {
      toast.error(t("users.loadError"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => { load(); }, [load]);

  async function handleCreate(e) {
    e.preventDefault();
    setFormError("");
    setFormLoading(true);
    try {
      const { data } = await createUser(form);
      setUsers(prev => [data, ...prev]);
      setTotal(t => t + 1);
      setForm(EMPTY_FORM);
      setShowForm(false);
      toast.success(t("users.created", { username: data.username }));
    } catch (err) {
      setFormError(extractApiError(err));
    } finally {
      setFormLoading(false);
    }
  }

  async function handleToggleActive(user) {
    if (toggling) return;
    setToggling(user.id);
    try {
      const { data } = await updateUser(user.id, { is_active: !user.is_active });
      setUsers(prev => prev.map(u => u.id === data.id ? data : u));
      toast.success(data.is_active ? t("users.activated") : t("users.deactivated"));
    } catch (err) {
      toast.error(extractApiError(err));
    } finally {
      setToggling(null);
    }
  }

  async function handleToggleRole(user) {
    if (toggling) return;
    setToggling(user.id);
    try {
      const newRole = user.role === "admin" ? "user" : "admin";
      const { data } = await updateUser(user.id, { role: newRole });
      setUsers(prev => prev.map(u => u.id === data.id ? data : u));
      toast.success(t("users.roleChanged", { role: data.role }));
    } catch (err) {
      toast.error(extractApiError(err));
    } finally {
      setToggling(null);
    }
  }

  async function handleDelete(user) {
    if (deleting) return;
    setDeleting(user.id);
    try {
      await deleteUser(user.id);
      setUsers(prev => prev.filter(u => u.id !== user.id));
      setTotal(t => t - 1);
      toast.success(t("users.deleted", { username: user.username }));
    } catch (err) {
      toast.error(extractApiError(err));
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">{t("users.title")}</h1>
          <p className="text-zinc-500 mt-1 text-sm">
            {total > 0 ? t("users.total", { count: total }) : t("users.empty")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={load} disabled={loading}>
            <RefreshCw size={14} className={loading ? "spin" : ""} />
          </Button>
          <Button size="sm" onClick={() => { setShowForm(v => !v); setFormError(""); }}>
            {showForm ? <X size={14} /> : <UserPlus size={14} />}
            {showForm ? t("common.close") : t("users.add")}
          </Button>
        </div>
      </div>

      {showForm && (
        <Card className="fade-in">
          <CardHeader title={t("users.form.title")} subtitle={t("users.form.subtitle")} />
          <form onSubmit={handleCreate} className="flex flex-col gap-4">
            <div className="grid sm:grid-cols-2 gap-4">
              <Input
                label="Username"
                placeholder="username"
                value={form.username}
                onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                hint={t("settings.account.usernameHint")}
                required
              />
              <div className="relative">
                <Input
                  label={t("users.form.password")}
                  type={showPw ? "text" : "password"}
                  placeholder={t("settings.security.minChars")}
                  value={form.password}
                  onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPw(v => !v)}
                  className="absolute right-3 bottom-2.5 text-zinc-600 hover:text-zinc-300 transition-colors"
                >
                  {showPw ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-zinc-300">Role</label>
              <div className="grid grid-cols-2 gap-2 sm:w-64">
                {["admin", "user"].map(r => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => setForm(f => ({ ...f, role: r }))}
                    className={`flex items-center gap-2 px-3 py-2.5 rounded-[10px] border text-sm font-medium transition-all
                      ${form.role === r
                        ? "bg-violet-500/15 border-violet-500/30 text-violet-300"
                        : "bg-white/3 border-white/8 text-zinc-500 hover:text-zinc-300 hover:bg-white/6"
                      }`}
                  >
                    {r === "admin" ? <Shield size={13} /> : <User2 size={13} />}
                    {r === "admin" ? "Admin" : "User"}
                  </button>
                ))}
              </div>
            </div>

            {formError && (
              <div className="rounded-xl bg-red-500/8 border border-red-500/18 px-4 py-3 text-sm text-red-400">
                {formError}
              </div>
            )}

            <div className="flex items-center gap-3">
              <Button type="submit" loading={formLoading}>
                <UserPlus size={14} /> {t("users.form.create")}
              </Button>
              <Button type="button" variant="ghost" onClick={() => { setShowForm(false); setForm(EMPTY_FORM); }}>
                {t("common.cancel")}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-zinc-600 text-sm py-4">
          <Spinner size={16} className="text-violet-400" /> {t("common.loading")}
        </div>
      ) : users.length === 0 ? (
        <Card>
          <div className="flex flex-col items-center gap-4 py-12 text-center">
            <div className="w-14 h-14 rounded-2xl bg-white/3 border border-white/8 flex items-center justify-center">
              <User2 size={22} className="text-zinc-600" />
            </div>
            <p className="text-zinc-500">{t("users.empty")}</p>
            <Button size="sm" onClick={() => setShowForm(true)}>
              <UserPlus size={14} /> {t("users.addFirst")}
            </Button>
          </div>
        </Card>
      ) : (
        <div className="flex flex-col gap-1.5">
          <div className="hidden sm:grid gap-4 px-5 text-[11px] text-zinc-600 uppercase tracking-wider font-semibold"
            style={{ gridTemplateColumns: "1fr 90px 100px 80px" }}>
            <span>{t("users.table.user")}</span>
            <span>{t("users.table.role")}</span>
            <span>{t("users.table.status")}</span>
            <span></span>
          </div>

          {users.map(u => {
            const isDel    = deleting === u.id;
            const isToggle = toggling === u.id;
            return (
              <div
                key={u.id}
                className={`table-row group ${isDel || isToggle ? "opacity-60 pointer-events-none" : ""}`}
                style={{ gridTemplateColumns: "1fr 90px 100px 80px" }}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-7 h-7 rounded-full bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center text-xs font-bold text-white shrink-0">
                    {u.username[0].toUpperCase()}
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-zinc-200 truncate">{u.username}</p>
                    <p className="text-[11px] text-zinc-700 mt-0.5">{timeAgo(u.created_at)}</p>
                  </div>
                </div>

                <div className="hidden sm:block">
                  <button
                    onClick={() => handleToggleRole(u)}
                    title={t("users.toggleRole")}
                    className="hover:opacity-70 transition-opacity"
                  >
                    <RoleBadge role={u.role} />
                  </button>
                </div>

                <div className="hidden sm:flex items-center">
                  <button
                    onClick={() => handleToggleActive(u)}
                    className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border transition-all
                      ${u.is_active
                        ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400 hover:bg-emerald-500/20"
                        : "bg-zinc-500/10 border-zinc-500/20 text-zinc-500 hover:bg-zinc-500/20"
                      }`}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${u.is_active ? "bg-emerald-400" : "bg-zinc-500"}`} />
                    {u.is_active ? t("users.active") : t("users.inactive")}
                  </button>
                </div>

                <div className="flex items-center justify-end">
                  <button
                    onClick={() => handleDelete(u)}
                    disabled={isDel}
                    title={t("common.delete")}
                    className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-zinc-700 hover:text-red-400 hover:bg-red-500/10 transition-all"
                  >
                    {isDel ? <Spinner size={13} /> : <Trash2 size={13} />}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
