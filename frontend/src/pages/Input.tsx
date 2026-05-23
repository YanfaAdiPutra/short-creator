import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, sourceUrl } from "../api";
import { useStore } from "../store";

export default function InputPage() {
  const project = useStore((s) => s.project);
  const setStep = useStore((s) => s.setStep);
  const loadProject = useStore((s) => s.loadProject);
  const navigate = useNavigate();
  const [pollingJob, setPollingJob] = useState(false);

  // If the user just created a from-url project, a download job is running.
  useEffect(() => {
    if (!project) return;
    if (project.video_meta) return; // already downloaded
    // Poll for the latest job by checking if source exists periodically.
    // We can simply re-fetch the project every couple of seconds.
    setPollingJob(true);
    const interval = setInterval(async () => {
      try {
        const p = await api.getProject(project.id);
        if (p.video_meta) {
          clearInterval(interval);
          await loadProject(project.id);
          setPollingJob(false);
        }
      } catch {}
    }, 2000);
    return () => clearInterval(interval);
  }, [project, loadProject]);

  if (!project) return null;

  return (
    <div className="p-8 max-w-3xl mx-auto space-y-6">
      <h2 className="text-2xl font-semibold">1. Input</h2>
      <div className="card space-y-3">
        <div className="label">Source</div>
        {project.source_url ? (
          <a
            href={project.source_url}
            target="_blank"
            rel="noreferrer"
            className="text-accent break-all"
          >
            {project.source_url}
          </a>
        ) : (
          <div className="text-slate-300">Uploaded file</div>
        )}
        <div className="text-xs text-slate-400">Project ID: {project.id}</div>
      </div>

      {project.video_meta ? (
        <>
          <div className="card grid grid-cols-2 gap-3 text-sm">
            <div>
              <div className="label">Resolution</div>
              {project.video_meta.width} × {project.video_meta.height}
            </div>
            <div>
              <div className="label">Duration</div>
              {project.video_meta.duration.toFixed(1)} s
            </div>
            <div>
              <div className="label">FPS</div>
              {project.video_meta.fps}
            </div>
            <div>
              <div className="label">Audio</div>
              {project.video_meta.has_audio ? "yes" : "no"}
            </div>
          </div>

          <video
            controls
            src={sourceUrl(project.id)}
            className="w-full rounded-lg bg-black"
          />

          <div className="flex justify-end gap-2">
            <button
              className="btn-primary"
              onClick={async () => {
                await setStep("transcribe");
                navigate(`/p/${project.id}/transcribe`);
              }}
            >
              Continue → Transcribe
            </button>
          </div>
        </>
      ) : (
        <div className="card text-center text-slate-400 py-8">
          {pollingJob ? "Downloading video…" : "Waiting for source video…"}
        </div>
      )}
    </div>
  );
}
