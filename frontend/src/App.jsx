import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./contexts/AuthContext";
import { AppLayout } from "./components/layout/AppLayout";
import { Spinner } from "./components/ui/Spinner";

// Route-based code-splitting: each page is its own chunk, loaded on demand,
// so the initial bundle stays small instead of shipping every page up front.
const LoginPage        = lazy(() => import("./pages/LoginPage"));
const DashboardPage    = lazy(() => import("./pages/DashboardPage"));
const NewVideoPage     = lazy(() => import("./pages/NewVideoPage"));
const VideoEditorPage  = lazy(() => import("./pages/VideoEditorPage"));
const NewSubtitlePage  = lazy(() => import("./pages/NewSubtitlePage"));
const NewTranscribePage = lazy(() => import("./pages/NewTranscribePage"));
const NewCleanupPage   = lazy(() => import("./pages/NewCleanupPage"));
const NewSeparatePage  = lazy(() => import("./pages/NewSeparatePage"));
const JobPage          = lazy(() => import("./pages/JobPage"));
const HistoryPage      = lazy(() => import("./pages/HistoryPage"));
const SettingsPage     = lazy(() => import("./pages/SettingsPage"));
const UsersPage        = lazy(() => import("./pages/UsersPage"));
const NewTtsPage       = lazy(() => import("./pages/NewTtsPage"));
const NewDubPage       = lazy(() => import("./pages/NewDubPage"));
const AudioHistoryPage = lazy(() => import("./pages/AudioHistoryPage"));
const NewImagePage     = lazy(() => import("./pages/NewImagePage"));
const NewImg2ShortPage = lazy(() => import("./pages/NewImg2ShortPage"));
const ImageHistoryPage = lazy(() => import("./pages/ImageHistoryPage"));
const ToolsPage        = lazy(() => import("./pages/ToolsPage"));
const ToolRunnerPage   = lazy(() => import("./pages/ToolRunnerPage"));
const ImageToolPage    = lazy(() => import("./pages/ImageToolPage"));
const AudioMergePage   = lazy(() => import("./pages/AudioMergePage"));
const VideoMergePage   = lazy(() => import("./pages/VideoMergePage"));

function PageFallback() {
  return (
    <div className="flex items-center justify-center h-full min-h-[50vh] text-violet-400">
      <Spinner size={28} />
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Suspense fallback={<PageFallback />}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />

            <Route element={<AppLayout />}>
              <Route path="/dashboard"          element={<DashboardPage />} />

              {/* ── Video ─────────────────────────────────────────── */}
              <Route path="/video/new"          element={<NewVideoPage />} />
              <Route path="/video/editor"       element={<VideoEditorPage />} />
              <Route path="/video/merge"        element={<VideoMergePage />} />
              <Route path="/video/subtitle"     element={<NewSubtitlePage />} />
              <Route path="/video/transcribe"   element={<NewTranscribePage />} />
              <Route path="/video/cleanup"      element={<NewCleanupPage />} />
              <Route path="/video/separate"     element={<NewSeparatePage />} />
              <Route path="/video/dub"          element={<NewDubPage />} />
              <Route path="/video/tool/:op"     element={<ToolRunnerPage />} />
              <Route path="/video/history"      element={<HistoryPage />} />
              <Route path="/job/:videoId"       element={<JobPage />} />

              {/* ── Audio ─────────────────────────────────────────── */}
              <Route path="/audio/new"          element={<NewTtsPage />} />
              <Route path="/audio/transcribe"   element={<NewTranscribePage />} />
              <Route path="/audio/cleanup"      element={<NewCleanupPage />} />
              <Route path="/audio/separate"     element={<NewSeparatePage />} />
              <Route path="/audio/dub"          element={<NewDubPage />} />
              <Route path="/audio/tool/:op"     element={<ToolRunnerPage />} />
              <Route path="/audio/merge/:op"    element={<AudioMergePage />} />
              <Route path="/audio/history"      element={<AudioHistoryPage />} />

              {/* ── Image ─────────────────────────────────────────── */}
              <Route path="/image/new"            element={<NewImagePage />} />
              <Route path="/image/to-shorts"      element={<NewImg2ShortPage />} />
              <Route path="/image/tool/:op"       element={<ImageToolPage />} />
              <Route path="/image/history"        element={<ImageHistoryPage />} />

              {/* ── Tools & System ────────────────────────────────── */}
              <Route path="/tools"              element={<ToolsPage />} />
              <Route path="/settings"           element={<SettingsPage />} />
              <Route path="/users"              element={<UsersPage />} />

              {/* ── Legacy paths → redirect to the unified scheme ──── */}
              <Route path="/new"        element={<Navigate to="/video/new" replace />} />
              <Route path="/subtitle"   element={<Navigate to="/video/subtitle" replace />} />
              <Route path="/cleanup"    element={<Navigate to="/video/cleanup" replace />} />
              <Route path="/separate"   element={<Navigate to="/video/separate" replace />} />
              <Route path="/dub"        element={<Navigate to="/video/dub" replace />} />
              <Route path="/history"    element={<Navigate to="/video/history" replace />} />
              <Route path="/transcribe" element={<Navigate to="/audio/transcribe" replace />} />
              <Route path="/photos/new"           element={<Navigate to="/image/new" replace />} />
              <Route path="/photos/to-shorts"     element={<Navigate to="/image/to-shorts" replace />} />
              <Route path="/photos/history"       element={<Navigate to="/image/history" replace />} />
              <Route path="/images/new"     element={<Navigate to="/image/new" replace />} />
              <Route path="/images/history" element={<Navigate to="/image/history" replace />} />
            </Route>

            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </AuthProvider>
  );
}
