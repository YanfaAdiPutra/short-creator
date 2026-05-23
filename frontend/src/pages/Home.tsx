import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type ProjectListItem } from "../api";

export default function HomePage() {
  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement | null>(null);
  const navigate = useNavigate();

  async function refresh() {
    setProjects(await api.listProjects());
  }

  useEffect(() => {
    refresh().catch(() => {});
  }, []);

  async function startFromUrl() {
    if (!url.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const r = await api.createFromUrl(url.trim());
      navigate(`/p/${r.project_id}/input`);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function startFromFile(file: File) {
    setBusy(true);
    setError(null);
    try {
      const r = await api.createFromUpload(file);
      navigate(`/p/${r.project_id}/transcribe`);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-start justify-center p-10">
      <div className="w-full max-w-4xl space-y-10">
        <header>
          <h1 className="text-3xl font-bold">short-creator</h1>
          <p className="text-slate-400 mt-1">
            Drop a YouTube link or upload a video. Get a 9:16 short with
            karaoke subtitles and an LLM-picked clip.
          </p>
        </header>

        <section className="grid md:grid-cols-2 gap-4">
          <div className="card space-y-3">
            <div className="label">From YouTube</div>
            <input
              className="input"
              placeholder="https://youtube.com/watch?v=…"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && startFromUrl()}
            />
            <button
              className="btn-primary w-full"
              disabled={busy || !url.trim()}
              onClick={startFromUrl}
            >
              {busy ? "Starting…" : "Fetch & create project"}
            </button>
          </div>

          <div className="card space-y-3">
            <div className="label">Upload local video</div>
            <input
              ref={fileInput}
              type="file"
              accept="video/*"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) startFromFile(f);
              }}
            />
            <button
              className="btn-secondary w-full"
              disabled={busy}
              onClick={() => fileInput.current?.click()}
            >
              Choose file…
            </button>
            <p className="text-xs text-slate-500">
              MP4 / MKV / MOV — files stay on this machine.
            </p>
          </div>
        </section>

        {error && (
          <div className="card border-red-700 text-red-300 text-sm">{error}</div>
        )}

        <section>
          <div className="label mb-2">Existing projects</div>
          {projects.length === 0 ? (
            <div className="text-slate-500 text-sm">No projects yet.</div>
          ) : (
            <ul className="space-y-2">
              {projects.map((p) => (
                <li
                  key={p.id}
                  className="card flex items-center justify-between hover:bg-canvas-inset cursor-pointer"
                  onClick={() => navigate(`/p/${p.id}`)}
                >
                  <div>
                    <div className="font-medium">{p.title || p.id}</div>
                    <div className="text-xs text-slate-400">
                      {new Date(p.created_at).toLocaleString()} · step:{" "}
                      {p.current_step}
                    </div>
                  </div>
                  <span className="text-xs text-slate-500">→</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
