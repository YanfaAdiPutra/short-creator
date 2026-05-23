// Lightweight typed API client. Backend lives at /api (proxied in dev).

const BASE = "/api";

type FetchOpts = {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
};

async function request<T>(path: string, opts: FetchOpts = {}): Promise<T> {
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;
  if (opts.body !== undefined) {
    if (opts.body instanceof FormData) {
      body = opts.body;
    } else {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(opts.body);
    }
  }
  const resp = await fetch(`${BASE}${path}`, {
    method: opts.method ?? (opts.body ? "POST" : "GET"),
    headers,
    body,
    signal: opts.signal,
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`${resp.status}: ${text}`);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export type ProjectStep =
  | "input"
  | "transcribe"
  | "recommend"
  | "crop"
  | "style"
  | "export";

export type VideoMeta = {
  width: number;
  height: number;
  duration: number;
  fps: number;
  has_audio: boolean;
  title: string | null;
  source_url: string | null;
};

export type Project = {
  id: string;
  title: string | null;
  created_at: string;
  current_step: ProjectStep;
  source_url: string | null;
  video_meta: VideoMeta | null;
  selected_clip_id: string | null;
  selected_range: [number, number] | null;
};

export type ProjectListItem = {
  id: string;
  title: string | null;
  created_at: string;
  current_step: ProjectStep;
};

export type Word = { word: string; start: number; end: number };

export type TranscriptSegment = {
  start: number;
  end: number;
  text: string;
  words: Word[];
};

export type Transcript = {
  language: string | null;
  duration: number;
  segments: TranscriptSegment[];
};

export type ClipSuggestion = {
  id: string;
  start: number;
  end: number;
  title: string;
  hook: string;
  reason: string;
  score: number;
};

export type Recommendations = {
  generated_at_transcript_hash: string;
  clips: ClipSuggestion[];
};

export type RecommendationsView = {
  recommendations: Recommendations | null;
  is_stale: boolean;
  current_transcript_hash: string;
  available_providers: string[];
};

export type CropSegment = { start: number; end: number; x: number; y: number };

export type CropPlan = {
  source_width: number;
  source_height: number;
  output_width: number;
  output_height: number;
  segments: CropSegment[];
};

export type SubtitleStyle = {
  font_family: string;
  font_size: number;
  window_size: number;
  active_color: string;
  inactive_color: string;
  outline_color: string;
  outline_thickness: number;
  vertical_position: "top" | "middle" | "bottom";
};

export type JobStatus = {
  job_id: string;
  kind: "download" | "transcribe" | "recommend" | "render";
  state: "pending" | "running" | "done" | "error";
  progress: number;
  message: string;
  error: string | null;
};

export type EnvInfo = {
  version: string;
  providers: { anthropic: boolean; openai: boolean; ollama: boolean };
  gpu: { name: string; vram_gb: number; profile: string } | null;
  ffmpeg: { nvenc: boolean };
  recommended_whisper_model: string;
};

export const api = {
  // env
  env: () => request<EnvInfo>("/settings/env"),

  // projects
  listProjects: () => request<ProjectListItem[]>("/projects"),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  createFromUrl: (url: string, title?: string) =>
    request<{ project_id: string; job_id: string }>("/projects/from-url", {
      body: { url, title },
    }),
  createFromUpload: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<{ project_id: string }>("/projects/from-upload", { body: fd });
  },
  setStep: (id: string, step: ProjectStep) =>
    request(`/projects/${id}/step`, { method: "PUT", body: { step } }),
  setSelection: (id: string, start: number, end: number, clipId?: string | null) =>
    request(`/projects/${id}/selection`, {
      method: "PUT",
      body: { start, end, clip_id: clipId ?? null },
    }),

  // transcript
  startTranscribe: (id: string, model?: string) =>
    request<{ job_id: string }>(`/projects/${id}/transcript`, { body: { model } }),
  getTranscript: (id: string) => request<Transcript>(`/projects/${id}/transcript`),
  putTranscript: (id: string, transcript: Transcript) =>
    request(`/projects/${id}/transcript`, { method: "PUT", body: { transcript } }),

  // recommend
  startRecommend: (id: string, provider?: string, model?: string) =>
    request<{ job_id: string }>(`/projects/${id}/recommendations`, {
      body: { provider, model },
    }),
  getRecommendations: (id: string) =>
    request<RecommendationsView>(`/projects/${id}/recommendations`),

  // crop
  getCrop: (id: string) => request<CropPlan>(`/projects/${id}/crop`),
  putCrop: (id: string, plan: CropPlan) =>
    request(`/projects/${id}/crop`, { method: "PUT", body: plan }),

  // style
  getStyle: (id: string) => request<SubtitleStyle>(`/projects/${id}/style`),
  putStyle: (id: string, style: SubtitleStyle) =>
    request(`/projects/${id}/style`, { method: "PUT", body: style }),

  // render
  startRender: (id: string, burnSubtitles: boolean) =>
    request<{ job_id: string }>(`/projects/${id}/render`, {
      body: { burn_subtitles: burnSubtitles },
    }),

  // jobs
  getJob: (jobId: string) => request<JobStatus>(`/jobs/${jobId}`),
};

export function sourceUrl(projectId: string): string {
  return `${BASE}/projects/${projectId}/source`;
}

export function outputUrl(projectId: string): string {
  return `${BASE}/projects/${projectId}/output`;
}
