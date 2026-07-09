import { Navigate, Outlet } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import { ShieldOff, LogOut } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { useAuth } from "../../contexts/AuthContext";
import { Spinner } from "../ui/Spinner";

function BootScreen() {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="flex flex-col items-center gap-4">
        <Spinner size={32} className="text-violet-500" />
        <p className="text-xs text-zinc-600 tracking-widest uppercase">Yuklanmoqda</p>
      </div>
    </div>
  );
}

function ForbiddenScreen({ user, logout }) {
  return (
    <div className="flex items-center justify-center min-h-screen p-6">
      <div className="flex flex-col items-center gap-6 text-center max-w-sm">
        <div className="w-20 h-20 rounded-3xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
          <ShieldOff size={32} className="text-red-400" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-zinc-100 mb-2">Kirish taqiqlangan</h1>
          <p className="text-sm text-zinc-500">
            Bu panel faqat <span className="text-zinc-300 font-medium">admin</span> foydalanuvchilar
            uchun mo'ljallangan.{" "}
            <span className="text-zinc-400">@{user?.username}</span> hisobi admin huquqiga ega emas.
          </p>
        </div>
        <button
          onClick={logout}
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm font-medium hover:bg-red-500/15 transition-all"
        >
          <LogOut size={16} /> Chiqish
        </button>
      </div>
    </div>
  );
}

export function AppLayout() {
  const { user, loading, logout } = useAuth();

  if (loading) return <BootScreen />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "admin" && user.role !== "superadmin") return <ForbiddenScreen user={user} logout={logout} />;

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Header />
        <main className="flex-1 overflow-auto">
          <div className="max-w-7xl mx-auto px-6 py-8 fade-in">
            <Outlet />
          </div>
        </main>
      </div>
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: "#13132a",
            color: "#dde0f0",
            border: "1px solid rgba(124,58,237,0.2)",
            borderRadius: "12px",
            fontSize: "13.5px",
            boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
          },
          success: { iconTheme: { primary: "#10b981", secondary: "#fff" } },
          error:   { iconTheme: { primary: "#ef4444", secondary: "#fff" } },
        }}
      />
    </div>
  );
}
