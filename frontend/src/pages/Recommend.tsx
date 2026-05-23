import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useStore } from "../store";

function fmtTime(s: number): string {
  const m = Math.floor(s / 60);
  const r = (s % 60).toFixed(1);
  return `${m}:${r.padStart(4, "0")}`;
}

export default function RecommendPage() {
  const project = useStore((s) => s.project);
  const env = useStore((s) => s.env);
  const recommendations = useStore((s) => s.recommendations);
  const stale = useStore((s) => s.recommendationsStale);
  const refresh = useStore((s) => s.refreshRecommendations);
  const trackJob = useStore((s) => s.trackJob);
  const setSelection = useStore((s) => s.setSelection);
  const setStep = useStore((s) => s.setStep);
  const navigate = useNavigate();
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<{ pct: number; msg: string } | null>(null);

  const providers = env?.providers || { anthropic: false, openai: false, ollama: false };
  const hasAny = Object.values(providers).some(Boolean);

  async function run() {
    if (!project) return;
    setRunning(true);
    setProgress({ pct: 0, msg: "Starting…" });
    try {
      const { job_id } = await api.startRecommend(project.id);
      const interval = setInterval(async () => {
        const job = await api.getJob(job_id);
        setProgress({ pct: job.progress, msg: job.message });
        if (job.state === "done" || job.state === "error") clearInterval(interval);
      }, 800);
      await trackJob(job_id);
      clearInterval(interval);
      await refresh();
    } catch (e) {
      setProgress({ pct: 0, msg: `Error: ${e}` });
    }
    setRunning(false);
  }

  async function pickClip(start: number, end: number, clipId: string) {
    if (!project) return;
    await setSelection(start, end, clipId);
    await setStep("crop");
    navigate(`/p/${project.id}/crop`);
  }

  async function skipToFullVideo() {
    if (!project?.video_meta) return;
    await setSelection(0, project.video_meta.duration, null);
    await setStep("crop");
    navigate(`/p/${project.id}/crop`);
  }

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      <h2 className="text-2xl font-semibold">3. Smart clip recommendations</h2>

      {!hasAny ? (
        <div className="card border-amber-700 text-amber-200 text-sm space-y-2">
          <div className="font-medium">No LLM provider configured</div>
          <p>
            Set one of these environment variables before launching:{" "}
            <code>ANTHROPIC_API_KEY</code>, <code>OPENAI_API_KEY</code>, or{" "}
            <code>OLLAMA_HOST</code>. Then restart the server and reload this
            page.
          </p>
          <button className="btn-ghost" onClick={skipToFullVideo}>
            Skip & use the full video →
          </button>
        </div>
      ) : (
        <div className="card flex items-center justify-between">
          <div className="text-sm text-slate-300">
            Using:{" "}
            {Object.entries(providers)
              .filter(([, v]) => v)
              .map(([k]) => k)
              .join(", ")}
          </div>
          <button className="btn-primary" disabled={running} onClick={run}>
            {running
              ? "Analyzing…"
              : recommendations
                ? "Re-analyze"
                : "Analyze transcript"}
          </button>
        </div>
      )}

      {progress && running && (
        <div className="text-xs text-slate-400">
          {progress.pct.toFixed(0)}% — {progress.msg}
        </div>
      )}

      {stale && recommendations && (
        <div className="card border-amber-600 text-amber-200 text-sm">
          Transcript changed since these were generated. They may be stale —
          click <strong>Re-analyze</strong> to refresh.
        </div>
      )}

      {recommendations && recommendations.clips.length > 0 ? (
        <ul className="grid md:grid-cols-2 gap-3">
          {recommendations.clips.map((c) => (
            <li key={c.id} className="card hover:bg-canvas-inset cursor-pointer space-y-2"
                onClick={() => pickClip(c.start, c.end, c.id)}>
              <div className="flex items-center justify-between">
                <div className="font-medium">{c.title || "Untitled"}</div>
                <div className="text-xs px-2 py-0.5 rounded bg-emerald-700/40 text-emerald-300">
                  {c.score}
                </div>
              </div>
              <div className="text-xs text-slate-400">
                {fmtTime(c.start)} – {fmtTime(c.end)} ·{" "}
                {(c.end - c.start).toFixed(1)}s
              </div>
              <div className="text-sm text-slate-300 italic">
                "{c.hook}"
              </div>
              <div className="text-xs text-slate-500">{c.reason}</div>
            </li>
          ))}
        </ul>
      ) : (
        recommendations && (
          <div className="text-slate-500">No clips returned by the LLM.</div>
        )
      )}

      <div className="flex justify-end">
        <button className="btn-ghost" onClick={skipToFullVideo}>
          Skip & use the full video →
        </button>
      </div>
    </div>
  );
}
