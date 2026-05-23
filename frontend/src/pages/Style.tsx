import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { SubtitleStyle } from "../api";
import { api } from "../api";
import { useStore } from "../store";

const FONTS = ["Arial Black", "Impact", "Bebas Neue", "Montserrat Black", "Anton"];

export default function StylePage() {
  const project = useStore((s) => s.project);
  const stored = useStore((s) => s.style);
  const refresh = useStore((s) => s.refreshStyle);
  const setStep = useStore((s) => s.setStep);
  const navigate = useNavigate();
  const [style, setStyle] = useState<SubtitleStyle | null>(stored);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setStyle(stored);
  }, [stored]);

  if (!project || !style) return null;

  function set<K extends keyof SubtitleStyle>(k: K, v: SubtitleStyle[K]) {
    setStyle((s) => (s ? { ...s, [k]: v } : s));
  }

  async function save() {
    if (!project || !style) return;
    setSaving(true);
    await api.putStyle(project.id, style);
    await refresh();
    setSaving(false);
  }

  async function continueExport() {
    await save();
    if (!project) return;
    await setStep("export");
    navigate(`/p/${project.id}/export`);
  }

  return (
    <div className="p-8 max-w-3xl mx-auto space-y-6">
      <h2 className="text-2xl font-semibold">5. Subtitle style</h2>

      <div className="card grid grid-cols-2 gap-4">
        <Field label="Font family">
          <select
            className="input"
            value={style.font_family}
            onChange={(e) => set("font_family", e.target.value)}
          >
            {FONTS.map((f) => (
              <option key={f}>{f}</option>
            ))}
          </select>
        </Field>
        <Field label="Font size">
          <input
            type="number"
            className="input"
            value={style.font_size}
            onChange={(e) => set("font_size", Number(e.target.value))}
          />
        </Field>
        <Field label="Words visible (window)">
          <select
            className="input"
            value={style.window_size}
            onChange={(e) => set("window_size", Number(e.target.value))}
          >
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n}>{n}</option>
            ))}
          </select>
        </Field>
        <Field label="Vertical position">
          <select
            className="input"
            value={style.vertical_position}
            onChange={(e) => set("vertical_position", e.target.value as any)}
          >
            <option value="top">Top</option>
            <option value="middle">Middle</option>
            <option value="bottom">Bottom</option>
          </select>
        </Field>
        <Field label="Active color (ASS &HBBGGRR&)">
          <input
            className="input"
            value={style.active_color}
            onChange={(e) => set("active_color", e.target.value)}
          />
        </Field>
        <Field label="Inactive color">
          <input
            className="input"
            value={style.inactive_color}
            onChange={(e) => set("inactive_color", e.target.value)}
          />
        </Field>
        <Field label="Outline color">
          <input
            className="input"
            value={style.outline_color}
            onChange={(e) => set("outline_color", e.target.value)}
          />
        </Field>
        <Field label="Outline thickness">
          <input
            type="number"
            className="input"
            value={style.outline_thickness}
            onChange={(e) => set("outline_thickness", Number(e.target.value))}
          />
        </Field>
      </div>

      <div className="card text-xs text-slate-400 space-y-1">
        <p>
          Subtitle preview is rendered at export time. ASS color format is{" "}
          <code>&amp;H</code> + alpha + BGR hex, e.g. <code>&amp;H0000FFFF&amp;</code>{" "}
          for yellow.
        </p>
        <p>
          Subtitles use the rolling-window karaoke effect: <strong>{style.window_size}</strong> words
          are visible at a time with the active one highlighted in the active color.
        </p>
      </div>

      <div className="flex justify-end gap-2">
        <button className="btn-secondary" disabled={saving} onClick={save}>
          {saving ? "Saving…" : "Save style"}
        </button>
        <button className="btn-primary" onClick={continueExport}>
          Continue → Export
        </button>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="label">{label}</div>
      {children}
    </label>
  );
}
