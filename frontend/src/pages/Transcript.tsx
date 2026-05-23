import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useStore } from "../store";

export default function TranscriptPage() {
  const project = useStore((s) => s.project);
  const transcript = useStore((s) => s.transcript);
  const env = useStore((s) => s.env);
  const refreshTranscript = useStore((s) => s.refreshTranscript);
  const trackJob = useStore((s) => s.trackJob);
  const setStep = useStore((s) => s.setStep);
  const navigate = useNavigate();
  const [model, setModel] = useState<string>("");
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<{ pct: number; msg: string } | null>(null);

  if (!project) return null;

  async function start() {
    if (!project) return;
    setRunning(true);
    setProgress({ pct: 0, msg: "Starting…" });
    const { job_id } = await api.startTranscribe(project.id, model || undefined);
    // Poll job status manually to surface progress here too.
    const interval = setInterval(async () => {
      const job = await api.getJob(job_id);
      setProgress({ pct: job.progress, msg: job.message });
      if (job.state === "done" || job.state === "error") clearInterval(interval);
    }, 800);
    await trackJob(job_id);
    clearInterval(interval);
    await refreshTranscript();
    setRunning(false);
  }

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">
      <h2 className="text-2xl font-semibold">2. Transcribe</h2>

      <div className="card space-y-3">
        <div className="label">Whisper model</div>
        <select
          className="input"
          value={model || env?.recommended_whisper_model || "medium"}
          onChange={(e) => setModel(e.target.value)}
        >
          {["tiny", "base", "small", "medium", "large-v3"].map((m) => (
            <option key={m} value={m}>
              {m}
              {m === env?.recommended_whisper_model && "  (recommended)"}
            </option>
          ))}
        </select>
        <button
          className="btn-primary"
          disabled={running}
          onClick={start}
        >
          {running ? "Transcribing…" : transcript ? "Re-transcribe" : "Start transcription"}
        </button>
        {progress && (
          <div className="text-xs text-slate-400">
            <div className="w-full h-1 bg-slate-700 rounded">
              <div
                className="h-1 bg-accent rounded transition-all"
                style={{ width: `${progress.pct}%` }}
              />
            </div>
            <div className="mt-1">
              {progress.pct.toFixed(0)}% — {progress.msg}
            </div>
          </div>
        )}
      </div>

      {transcript && (
        <>
          <div className="card text-xs text-slate-400">
            Language: {transcript.language || "unknown"} · Duration:{" "}
            {transcript.duration.toFixed(1)}s · Segments:{" "}
            {transcript.segments.length} · Words:{" "}
            {transcript.segments.reduce((acc, s) => acc + s.words.length, 0)}
          </div>

          <div className="card max-h-[60vh] overflow-y-auto space-y-2">
            {transcript.segments.map((seg, i) => (
              <div key={i} className="text-sm">
                <span className="text-slate-500 text-xs mr-2">
                  [{seg.start.toFixed(1)}s]
                </span>
                {seg.text}
              </div>
            ))}
          </div>

          <div className="flex justify-end gap-2">
            <button
              className="btn-primary"
              onClick={async () => {
                if (!project) return;
                await setStep("recommend");
                navigate(`/p/${project.id}/recommend`);
              }}
            >
              Continue → Recommend
            </button>
          </div>
        </>
      )}
    </div>
  );
}
