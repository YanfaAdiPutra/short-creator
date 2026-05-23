import { useEffect, useRef, useState } from "react";
import type { CropPlan, CropSegment } from "../api";

type Props = {
  videoEl: HTMLVideoElement | null;
  plan: CropPlan;
  activeSegmentIndex: number;
  onSegmentChange: (index: number, seg: CropSegment) => void;
};

/**
 * Renders the source video frame with a draggable 9:16 crop rectangle overlay.
 * The rectangle's width matches the active segment's source-pixel dimensions
 * (plan.output_width / plan.output_height), centered vertically.
 */
export function CropCanvas({
  videoEl,
  plan,
  activeSegmentIndex,
  onSegmentChange,
}: Props) {
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const [wrapWidth, setWrapWidth] = useState(640);
  const [dragOffset, setDragOffset] = useState<{
    dx: number;
    dy: number;
    startX: number;
    startY: number;
  } | null>(null);

  const seg = plan.segments[activeSegmentIndex];

  // Aspect-fit the source video into wrapWidth.
  const srcAspect = plan.source_width / plan.source_height;
  const displayWidth = wrapWidth;
  const displayHeight = wrapWidth / srcAspect;
  const scale = displayWidth / plan.source_width;

  useEffect(() => {
    if (!wrapRef.current) return;
    const obs = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 640;
      setWrapWidth(w);
    });
    obs.observe(wrapRef.current);
    return () => obs.disconnect();
  }, []);

  // Drag the crop box
  function onMouseDown(e: React.MouseEvent) {
    if (!seg) return;
    setDragOffset({
      dx: e.clientX,
      dy: e.clientY,
      startX: seg.x,
      startY: seg.y,
    });
    e.preventDefault();
  }

  useEffect(() => {
    if (!dragOffset || !seg) return;
    function move(e: MouseEvent) {
      const ddx = (e.clientX - dragOffset!.dx) / scale;
      const ddy = (e.clientY - dragOffset!.dy) / scale;
      const newX = Math.max(
        0,
        Math.min(
          plan.source_width - plan.output_width,
          Math.round(dragOffset!.startX + ddx),
        ),
      );
      const newY = Math.max(
        0,
        Math.min(
          plan.source_height - plan.output_height,
          Math.round(dragOffset!.startY + ddy),
        ),
      );
      onSegmentChange(activeSegmentIndex, { ...seg!, x: newX, y: newY });
    }
    function up() {
      setDragOffset(null);
    }
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    return () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
  }, [dragOffset, scale, seg, plan, activeSegmentIndex, onSegmentChange]);

  return (
    <div
      ref={wrapRef}
      className="relative w-full bg-black rounded-lg overflow-hidden"
      style={{ aspectRatio: `${plan.source_width} / ${plan.source_height}` }}
    >
      {videoEl && (
        <VideoFrameMirror videoEl={videoEl} className="absolute inset-0 w-full h-full" />
      )}
      {seg && (
        <div
          onMouseDown={onMouseDown}
          className="absolute border-2 border-accent shadow-lg cursor-move ring-2 ring-accent/40"
          style={{
            left: seg.x * scale,
            top: seg.y * scale,
            width: plan.output_width * scale,
            height: plan.output_height * scale,
          }}
        >
          <div className="absolute -top-7 left-0 text-xs px-2 py-0.5 bg-accent text-slate-900 rounded">
            crop · {seg.start.toFixed(1)}–{seg.end.toFixed(1)}s
          </div>
          <Corner pos="tl" />
          <Corner pos="tr" />
          <Corner pos="bl" />
          <Corner pos="br" />
        </div>
      )}
      <div className="absolute inset-0 pointer-events-none border-2 border-slate-700" />
    </div>
  );
}

function Corner({ pos }: { pos: "tl" | "tr" | "bl" | "br" }) {
  const classes = {
    tl: "top-0 left-0",
    tr: "top-0 right-0",
    bl: "bottom-0 left-0",
    br: "bottom-0 right-0",
  } as const;
  return (
    <div
      className={`absolute w-3 h-3 bg-accent ${classes[pos]} pointer-events-none`}
    />
  );
}

/**
 * Mirrors the current frame of a <video> element onto a sibling <canvas> using
 * requestAnimationFrame. This lets us show the source video full-bleed without
 * embedding a second <video> element (which would double-decode and double the
 * VRAM footprint).
 */
function VideoFrameMirror({
  videoEl,
  className,
}: {
  videoEl: HTMLVideoElement;
  className?: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    let raf = 0;
    const draw = () => {
      const canvas = canvasRef.current;
      if (!canvas || !videoEl.videoWidth) {
        raf = requestAnimationFrame(draw);
        return;
      }
      if (canvas.width !== videoEl.videoWidth) {
        canvas.width = videoEl.videoWidth;
        canvas.height = videoEl.videoHeight;
      }
      const ctx = canvas.getContext("2d");
      if (ctx) ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height);
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(raf);
  }, [videoEl]);

  return <canvas ref={canvasRef} className={className} />;
}
