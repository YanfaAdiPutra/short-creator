import type { CropPlan } from "../api";

type Props = {
  duration: number;
  currentTime: number;
  plan: CropPlan;
  activeIndex: number;
  clipRange: [number, number];
  onSeek: (t: number) => void;
  onSelectSegment: (i: number) => void;
};

export function Timeline({
  duration,
  currentTime,
  plan,
  activeIndex,
  clipRange,
  onSeek,
  onSelectSegment,
}: Props) {
  return (
    <div className="space-y-2">
      <div
        className="relative h-12 bg-slate-800 rounded cursor-pointer select-none"
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const ratio = (e.clientX - rect.left) / rect.width;
          onSeek(clipRange[0] + ratio * (clipRange[1] - clipRange[0]));
        }}
      >
        {plan.segments.map((seg, i) => {
          const segStart = Math.max(seg.start, clipRange[0]);
          const segEnd = Math.min(seg.end, clipRange[1]);
          if (segEnd <= segStart) return null;
          const left = ((segStart - clipRange[0]) / (clipRange[1] - clipRange[0])) * 100;
          const width = ((segEnd - segStart) / (clipRange[1] - clipRange[0])) * 100;
          return (
            <div
              key={i}
              onClick={(e) => {
                e.stopPropagation();
                onSelectSegment(i);
              }}
              className={`absolute top-0 bottom-0 border-r-2 ${
                i === activeIndex
                  ? "bg-accent/30 border-accent"
                  : "bg-slate-700/40 border-slate-600 hover:bg-slate-700/70"
              }`}
              style={{ left: `${left}%`, width: `${width}%` }}
              title={`Segment ${i + 1}`}
            >
              <span className="absolute top-1 left-1 text-[10px] text-slate-300">
                #{i + 1}
              </span>
            </div>
          );
        })}
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-red-400 pointer-events-none"
          style={{
            left: `${
              ((currentTime - clipRange[0]) / (clipRange[1] - clipRange[0])) * 100
            }%`,
          }}
        />
      </div>
      <div className="flex justify-between text-xs text-slate-500">
        <span>{clipRange[0].toFixed(1)}s</span>
        <span>{currentTime.toFixed(1)}s</span>
        <span>{clipRange[1].toFixed(1)}s</span>
      </div>
    </div>
  );
}
