import { create } from "zustand";
import type {
  CropPlan,
  EnvInfo,
  JobStatus,
  Project,
  ProjectStep,
  Recommendations,
  SubtitleStyle,
  Transcript,
} from "./api";
import { api } from "./api";

type ProjectState = {
  env: EnvInfo | null;
  project: Project | null;
  transcript: Transcript | null;
  recommendations: Recommendations | null;
  recommendationsStale: boolean;
  crop: CropPlan | null;
  style: SubtitleStyle | null;
  activeJob: JobStatus | null;

  loadEnv: () => Promise<void>;
  loadProject: (id: string) => Promise<void>;
  refreshTranscript: () => Promise<void>;
  refreshRecommendations: () => Promise<void>;
  refreshCrop: () => Promise<void>;
  refreshStyle: () => Promise<void>;
  setStep: (step: ProjectStep) => Promise<void>;
  setSelection: (start: number, end: number, clipId?: string | null) => Promise<void>;
  trackJob: (jobId: string, onDone?: () => Promise<void> | void) => Promise<JobStatus>;
};

export const useStore = create<ProjectState>((set, get) => ({
  env: null,
  project: null,
  transcript: null,
  recommendations: null,
  recommendationsStale: false,
  crop: null,
  style: null,
  activeJob: null,

  async loadEnv() {
    set({ env: await api.env() });
  },

  async loadProject(id) {
    const project = await api.getProject(id);
    set({
      project,
      transcript: null,
      recommendations: null,
      crop: null,
      style: null,
      activeJob: null,
    });
    // Best-effort fetch of everything else; ignore 404s (not yet generated).
    try { await get().refreshTranscript(); } catch {}
    try { await get().refreshRecommendations(); } catch {}
    try { await get().refreshCrop(); } catch {}
    try { await get().refreshStyle(); } catch {}
  },

  async refreshTranscript() {
    const id = get().project?.id;
    if (!id) return;
    try {
      const t = await api.getTranscript(id);
      set({ transcript: t });
    } catch {
      set({ transcript: null });
    }
  },

  async refreshRecommendations() {
    const id = get().project?.id;
    if (!id) return;
    const view = await api.getRecommendations(id);
    set({
      recommendations: view.recommendations,
      recommendationsStale: view.is_stale,
    });
  },

  async refreshCrop() {
    const id = get().project?.id;
    if (!id) return;
    try {
      const c = await api.getCrop(id);
      set({ crop: c });
    } catch {
      set({ crop: null });
    }
  },

  async refreshStyle() {
    const id = get().project?.id;
    if (!id) return;
    const s = await api.getStyle(id);
    set({ style: s });
  },

  async setStep(step) {
    const id = get().project?.id;
    if (!id) return;
    await api.setStep(id, step);
    const project = await api.getProject(id);
    set({ project });
  },

  async setSelection(start, end, clipId) {
    const id = get().project?.id;
    if (!id) return;
    await api.setSelection(id, start, end, clipId ?? null);
    const project = await api.getProject(id);
    set({ project });
  },

  async trackJob(jobId, onDone) {
    return new Promise((resolve) => {
      const tick = async () => {
        try {
          const status = await api.getJob(jobId);
          set({ activeJob: status });
          if (status.state === "done") {
            if (onDone) await onDone();
            resolve(status);
            return;
          }
          if (status.state === "error") {
            resolve(status);
            return;
          }
        } catch {
          // Job not found anymore — stop polling.
          resolve({
            job_id: jobId,
            kind: "render",
            state: "error",
            progress: 0,
            message: "",
            error: "Job vanished",
          });
          return;
        }
        setTimeout(tick, 800);
      };
      tick();
    });
  },
}));
