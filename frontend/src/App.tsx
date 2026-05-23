import { useEffect } from "react";
import { Navigate, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import InputPage from "./pages/Input";
import TranscriptPage from "./pages/Transcript";
import RecommendPage from "./pages/Recommend";
import CropEditorPage from "./pages/CropEditor";
import StylePage from "./pages/Style";
import ExportPage from "./pages/Export";
import HomePage from "./pages/Home";
import { useStore } from "./store";

function ProjectShell({ children }: { children: React.ReactNode }) {
  const { projectId } = useParams<{ projectId: string }>();
  const project = useStore((s) => s.project);
  const loadProject = useStore((s) => s.loadProject);

  useEffect(() => {
    if (projectId && projectId !== project?.id) {
      loadProject(projectId);
    }
  }, [projectId, project?.id, loadProject]);

  if (projectId && !project) {
    return (
      <div className="h-full flex items-center justify-center text-slate-400">
        Loading project…
      </div>
    );
  }

  return (
    <div className="h-full flex">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar />
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
}

export default function App() {
  const loadEnv = useStore((s) => s.loadEnv);
  useEffect(() => {
    loadEnv();
  }, [loadEnv]);

  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route
        path="/p/:projectId/*"
        element={
          <ProjectShell>
            <Routes>
              <Route path="input" element={<InputPage />} />
              <Route path="transcribe" element={<TranscriptPage />} />
              <Route path="recommend" element={<RecommendPage />} />
              <Route path="crop" element={<CropEditorPage />} />
              <Route path="style" element={<StylePage />} />
              <Route path="export" element={<ExportPage />} />
              <Route path="*" element={<RedirectToCurrentStep />} />
            </Routes>
          </ProjectShell>
        }
      />
    </Routes>
  );
}

function RedirectToCurrentStep() {
  const project = useStore((s) => s.project);
  const navigate = useNavigate();
  useEffect(() => {
    if (project) {
      navigate(`/p/${project.id}/${project.current_step}`, { replace: true });
    }
  }, [project, navigate]);
  return null;
}
