import { useEffect, useRef } from "react";
import type { CropPlan } from "../api";

type Props = {
  videoEl: HTMLVideoElement | null;
  plan: CropPlan;
  activeSegmentIndex: number;
  className?: string;
};

/**
 * Live 9:16 preview — copies the current crop region of the source <video>
 * onto a vertical canvas. Updates every animation frame.
 */
export function PreviewPane({ videoEl, plan, activeSegmentIndex, className }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    let raf = 0;
    const draw = () => {
      const canvas = canvasRef.current;
      if (!canvas || !videoEl?.videoWidth) {
        raf = requestAnimationFrame(draw);
        return;
      }
      const seg = plan.segments[activeSegmentIndex];
      if (!seg) {
        raf = requestAnimationFrame(draw);
        return;
      }
      if (canvas.width !== plan.output_width) {
        canvas.width = plan.output_width;
        canvas.height = plan.output_height;
      }
      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.drawImage(
          videoEl,
          seg.x,
          seg.y,
          plan.output_width,
          plan.output_height,
          0,
          0,
          plan.output_width,
          plan.output_height,
        );
      }
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(raf);
  }, [videoEl, plan, activeSegmentIndex]);

  return (
    <div
      className={`bg-black rounded-lg overflow-hidden ${className || ""}`}
      style={{ aspectRatio: "9 / 16" }}
    >
      <canvas ref={canvasRef} className="w-full h-full object-contain" />
    </div>
  );
}
