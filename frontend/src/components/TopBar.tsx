import { useNavigate } from "react-router-dom";
import { useStore } from "../store";

export function TopBar() {
  const project = useStore((s) => s.project);
  const navigate = useNavigate();
  const job = useStore((s) => s.activeJob);

  return (
    <header className="h-12 border-b border-slate-800 flex items-center justify-between px-4 bg-canvas-panel/40">
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={() => navigate("/")}
          className="text-slate-400 hover:text-slate-100 text-sm"
        >
          ← All projects
        </button>
        <span className="text-slate-600">|</span>
        <span className="text-sm truncate">
          {project?.title || "Untitled"}
        </span>
      </div>
      <div className="flex items-center gap-2">
        {job && job.state === "running" && (
          <div className="flex items-center gap-2 text-xs text-accent">
            <span className="animate-pulse">●</span>
            <span>{job.message || job.kind}</span>
            <span>{job.progress.toFixed(0)}%</span>
          </div>
        )}
      </div>
    </header>
  );
}
