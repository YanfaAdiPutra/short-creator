import { useState } from "react";
import { api, outputUrl } from "../api";
import { useStore } from "../store";

export default function ExportPage() {
  const project = useStore((s) => s.project);
  const trackJob = useStore((s) => s.trackJob);
  const transcript = useStore((s) => s.transcript);
  const [burnSubs, setBurnSubs] = useState(true);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<{ pct: number; msg: string; state?: string; error?: string | null } | null>(null);
  const [renderedAt, setRenderedAt] = useState<number | null>(null);

  async function start() {
    if (!project) return;
    setRunning(true);
    setRenderedAt(null);
    setProgress({ pct: 0, msg: "Starting…" });
    const { job_id } = await api.startRender(project.id, burnSubs && !!transcript);
    const interval = setInterval(async () => {
      const job = await api.getJob(job_id);
      setProgress({
        pct: job.progress,
        msg: job.message,
        state: job.state,
        error: job.error,
      });
      if (job.state === "done" || job.state === "error") clearInterval(interval);
    }, 800);
    await trackJob(job_id);
    clearInterval(interval);
    setRunning(false);
    setRenderedAt(Date.now());
  }

  if (!project) return null;

  return (
    <div className="p-8 max-w-3xl mx-auto space-y-6">
      <h2 className="text-2xl font-semibold">6. Export</h2>

      <div className="card space-y-3">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={burnSubs}
            disabled={!transcript}
            onChange={(e) => setBurnSubs(e.target.checked)}
          />
          Burn karaoke subtitles into the video
          {!transcript && (
            <span className="text-xs text-slate-500">(transcript missing)</span>
          )}
        </label>

        <div className="text-xs text-slate-400">
          Selected range:{" "}
          {project.selected_range
            ? `${project.selected_range[0].toFixed(1)}s – ${project.selected_range[1].toFixed(1)}s`
            : "full video"}
        </div>

        <button className="btn-primary" disabled={running} onClick={start}>
          {running ? "Rendering…" : "Render 9:16 short"}
        </button>

        {progress && (
          <div className="space-y-2">
            <div className="w-full h-1.5 bg-slate-700 rounded">
              <div
                className="h-1.5 bg-accent rounded transition-all"
                style={{ width: `${progress.pct}%` }}
              />
            </div>
            <div className="text-xs text-slate-400">
              {progress.pct.toFixed(0)}% — {progress.msg}
            </div>
            {progress.error && (
              <pre className="text-xs text-red-300 whitespace-pre-wrap">
                {progress.error}
              </pre>
            )}
          </div>
        )}
      </div>

      {renderedAt && progress?.state === "done" && (
        <div className="card space-y-3">
          <div className="label">Output</div>
          <video
            controls
            src={`${outputUrl(project.id)}?ts=${renderedAt}`}
            className="w-full rounded bg-black"
          />
          <a
            href={`${outputUrl(project.id)}?ts=${renderedAt}`}
            download="short.mp4"
            className="btn-secondary inline-block"
          >
            Download MP4
          </a>
        </div>
      )}
    </div>
  );
}
