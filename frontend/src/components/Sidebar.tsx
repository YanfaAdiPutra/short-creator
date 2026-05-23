import { NavLink, useParams } from "react-router-dom";
import { useStore } from "../store";
import type { ProjectStep } from "../api";

const STEPS: { key: ProjectStep; label: string; sub: string }[] = [
  { key: "input", label: "1 · Input", sub: "Source video" },
  { key: "transcribe", label: "2 · Transcribe", sub: "Word timestamps" },
  { key: "recommend", label: "3 · Recommend", sub: "LLM clip picks" },
  { key: "crop", label: "4 · Crop", sub: "9:16 framing" },
  { key: "style", label: "5 · Style", sub: "Subtitle look" },
  { key: "export", label: "6 · Export", sub: "Render & save" },
];

export function Sidebar() {
  const { projectId } = useParams<{ projectId: string }>();
  const project = useStore((s) => s.project);
  const transcript = useStore((s) => s.transcript);
  const crop = useStore((s) => s.crop);

  const done: Record<ProjectStep, boolean> = {
    input: !!project?.video_meta,
    transcribe: !!transcript,
    recommend: !!project?.selected_range,
    crop: !!crop?.segments?.length,
    style: false,
    export: false,
  };

  return (
    <aside className="w-56 shrink-0 bg-canvas-panel border-r border-slate-800 flex flex-col">
      <div className="px-4 py-4 border-b border-slate-800">
        <div className="text-lg font-bold tracking-tight">short-creator</div>
        <div className="text-xs text-slate-400 truncate">
          {project?.title || "New project"}
        </div>
      </div>
      <nav className="flex-1 overflow-y-auto py-2">
        {STEPS.map((s) => (
          <NavLink
            key={s.key}
            to={`/p/${projectId}/${s.key}`}
            className={({ isActive }) =>
              `block px-4 py-3 border-l-2 ${
                isActive
                  ? "bg-slate-800/60 border-accent text-white"
                  : "border-transparent text-slate-300 hover:bg-slate-800/40"
              }`
            }
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">{s.label}</span>
              {done[s.key] && (
                <span className="text-[10px] uppercase tracking-wider text-emerald-400">
                  done
                </span>
              )}
            </div>
            <div className="text-xs text-slate-400">{s.sub}</div>
          </NavLink>
        ))}
      </nav>
      <div className="p-4 border-t border-slate-800 text-xs text-slate-500">
        <EnvBadge />
      </div>
    </aside>
  );
}

function EnvBadge() {
  const env = useStore((s) => s.env);
  if (!env) return <span>Loading env…</span>;
  return (
    <div className="space-y-1">
      <div>GPU: {env.gpu ? env.gpu.name : "none"}</div>
      <div>NVENC: {env.ffmpeg.nvenc ? "yes" : "no"}</div>
      <div>
        Provider:{" "}
        {Object.entries(env.providers)
          .filter(([, v]) => v)
          .map(([k]) => k)
          .join(", ") || "none"}
      </div>
    </div>
  );
}
