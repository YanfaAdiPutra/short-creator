import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { CropPlan, CropSegment } from "../api";
import { api, sourceUrl } from "../api";
import { CropCanvas } from "../components/CropCanvas";
import { PreviewPane } from "../components/PreviewPane";
import { Timeline } from "../components/Timeline";
import { useStore } from "../store";

export default function CropEditorPage() {
  const project = useStore((s) => s.project);
  const cropStored = useStore((s) => s.crop);
  const refreshCrop = useStore((s) => s.refreshCrop);
  const setStep = useStore((s) => s.setStep);
  const navigate = useNavigate();

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [videoEl, setVideoEl] = useState<HTMLVideoElement | null>(null);
  const [plan, setPlan] = useState<CropPlan | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [saving, setSaving] = useState(false);

  const clipRange: [number, number] = useMemo(() => {
    if (project?.selected_range) return project.selected_range;
    return [0, project?.video_meta?.duration ?? 0];
  }, [project]);

  useEffect(() => {
    setPlan(cropStored);
  }, [cropStored]);

  // Auto-seek to clip start when video loads
  useEffect(() => {
    if (!videoEl) return;
    function onLoad() {
      if (videoEl) videoEl.currentTime = clipRange[0];
    }
    function onTime() {
      if (videoEl) {
        setCurrentTime(videoEl.currentTime);
        if (videoEl.currentTime >= clipRange[1]) {
          videoEl.pause();
          videoEl.currentTime = clipRange[0];
        }
      }
    }
    function onPlay() {
      setPlaying(true);
    }
    function onPause() {
      setPlaying(false);
    }
    videoEl.addEventListener("loadedmetadata", onLoad);
    videoEl.addEventListener("timeupdate", onTime);
    videoEl.addEventListener("play", onPlay);
    videoEl.addEventListener("pause", onPause);
    return () => {
      videoEl.removeEventListener("loadedmetadata", onLoad);
      videoEl.removeEventListener("timeupdate", onTime);
      videoEl.removeEventListener("play", onPlay);
      videoEl.removeEventListener("pause", onPause);
    };
  }, [videoEl, clipRange]);

  // Auto-select segment that contains current playhead
  useEffect(() => {
    if (!plan) return;
    const i = plan.segments.findIndex(
      (s) => currentTime >= s.start && currentTime < s.end,
    );
    if (i !== -1 && i !== activeIndex) setActiveIndex(i);
  }, [currentTime, plan, activeIndex]);

  if (!project || !plan) return null;

  function updateSegment(i: number, seg: CropSegment) {
    if (!plan) return;
    const next = { ...plan, segments: plan.segments.map((s, idx) => (idx === i ? seg : s)) };
    setPlan(next);
  }

  function addCutHere() {
    if (!plan) return;
    const t = currentTime;
    const containingIndex = plan.segments.findIndex(
      (s) => t > s.start + 0.1 && t < s.end - 0.1,
    );
    if (containingIndex === -1) return;
    const orig = plan.segments[containingIndex];
    const head: CropSegment = { ...orig, end: t };
    const tail: CropSegment = { ...orig, start: t };
    const segments = [
      ...plan.segments.slice(0, containingIndex),
      head,
      tail,
      ...plan.segments.slice(containingIndex + 1),
    ];
    setPlan({ ...plan, segments });
    setActiveIndex(containingIndex + 1);
  }

  function deleteActiveSegment() {
    if (!plan || plan.segments.length <= 1) return;
    const segs = [...plan.segments];
    const removed = segs.splice(activeIndex, 1)[0];
    // Extend the neighbour to cover the removed range
    if (activeIndex > 0) {
      segs[activeIndex - 1] = { ...segs[activeIndex - 1], end: removed.end };
    } else if (segs.length > 0) {
      segs[0] = { ...segs[0], start: removed.start };
    }
    setPlan({ ...plan, segments: segs });
    setActiveIndex(Math.max(0, activeIndex - 1));
  }

  async function save() {
    if (!project || !plan) return;
    setSaving(true);
    try {
      await api.putCrop(project.id, plan);
      await refreshCrop();
    } finally {
      setSaving(false);
    }
  }

  async function continueToStyle() {
    if (!project) return;
    await save();
    await setStep("style");
    navigate(`/p/${project.id}/style`);
  }

  function seek(t: number) {
    if (videoEl) videoEl.currentTime = t;
  }

  function togglePlay() {
    if (!videoEl) return;
    if (videoEl.paused) videoEl.play();
    else videoEl.pause();
  }

  return (
    <div className="p-6 space-y-4 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">4. Crop editor</h2>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={save} disabled={saving}>
            {saving ? "Saving…" : "Save crop"}
          </button>
          <button className="btn-primary" onClick={continueToStyle}>
            Continue → Style
          </button>
        </div>
      </div>

      <video
        ref={(el) => {
          videoRef.current = el;
          setVideoEl(el);
        }}
        src={sourceUrl(project.id)}
        className="hidden"
        crossOrigin="anonymous"
      />

      <div className="grid grid-cols-[1fr,260px] gap-4">
        <CropCanvas
          videoEl={videoEl}
          plan={plan}
          activeSegmentIndex={activeIndex}
          onSegmentChange={updateSegment}
        />
        <PreviewPane
          videoEl={videoEl}
          plan={plan}
          activeSegmentIndex={activeIndex}
        />
      </div>

      <div className="card space-y-3">
        <div className="flex items-center gap-2">
          <button className="btn-secondary" onClick={togglePlay}>
            {playing ? "Pause" : "Play"}
          </button>
          <button className="btn-secondary" onClick={addCutHere}>
            + Cut here
          </button>
          <button
            className="btn-ghost"
            onClick={deleteActiveSegment}
            disabled={plan.segments.length <= 1}
          >
            Delete segment
          </button>
          <span className="text-xs text-slate-500 ml-auto">
            {plan.segments.length} segment{plan.segments.length === 1 ? "" : "s"}
          </span>
        </div>
        <Timeline
          duration={project.video_meta?.duration ?? 0}
          currentTime={currentTime}
          plan={plan}
          activeIndex={activeIndex}
          clipRange={clipRange}
          onSeek={seek}
          onSelectSegment={(i) => {
            setActiveIndex(i);
            seek(plan.segments[i].start);
          }}
        />
      </div>

      <SegmentList
        plan={plan}
        activeIndex={activeIndex}
        onSelect={setActiveIndex}
        onChange={updateSegment}
      />
    </div>
  );
}

function SegmentList({
  plan,
  activeIndex,
  onSelect,
  onChange,
}: {
  plan: CropPlan;
  activeIndex: number;
  onSelect: (i: number) => void;
  onChange: (i: number, seg: CropSegment) => void;
}) {
  return (
    <div className="card">
      <div className="label">Segments</div>
      <div className="space-y-1">
        {plan.segments.map((seg, i) => (
          <div
            key={i}
            className={`flex items-center gap-2 text-xs p-2 rounded cursor-pointer ${
              i === activeIndex ? "bg-accent/20" : "hover:bg-slate-800"
            }`}
            onClick={() => onSelect(i)}
          >
            <span className="w-6 text-slate-400">#{i + 1}</span>
            <span className="flex-1">
              {seg.start.toFixed(1)}s – {seg.end.toFixed(1)}s
            </span>
            <label className="flex items-center gap-1">
              x
              <input
                type="number"
                className="input w-16 text-xs py-1"
                value={seg.x}
                onChange={(e) =>
                  onChange(i, { ...seg, x: Number(e.target.value) || 0 })
                }
                onClick={(e) => e.stopPropagation()}
              />
            </label>
            <label className="flex items-center gap-1">
              y
              <input
                type="number"
                className="input w-16 text-xs py-1"
                value={seg.y}
                onChange={(e) =>
                  onChange(i, { ...seg, y: Number(e.target.value) || 0 })
                }
                onClick={(e) => e.stopPropagation()}
              />
            </label>
          </div>
        ))}
      </div>
    </div>
  );
}
