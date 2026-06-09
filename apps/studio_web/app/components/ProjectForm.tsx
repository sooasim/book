"use client";

import { useState } from "react";
import type { ProjectOptions } from "../lib/api";

const FIELD =
  "rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900";

export function ProjectForm({
  onSubmit,
  disabled,
}: {
  onSubmit: (opts: ProjectOptions & { provider: string; mode: string }) => void;
  disabled?: boolean;
}) {
  const [title, setTitle] = useState("제로존 입문");
  const [topic, setTopic] = useState("제로존 수학과 존재론");
  const [audience, setAudience] = useState("일반 교양 독자");
  const [tone, setTone] = useState("친근하고 명료한");
  const [nChapters, setNChapters] = useState(6);
  const [lengthTarget, setLengthTarget] = useState(6000);
  const [provider, setProvider] = useState("stub");
  const [mode, setMode] = useState("rules");

  return (
    <form
      className="flex flex-col gap-4 rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit({
          title,
          topic,
          audience,
          tone,
          n_chapters: nChapters,
          length_target: lengthTarget,
          provider,
          mode,
        });
      }}
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm font-medium">
          제목
          <input className={FIELD} value={title} onChange={(e) => setTitle(e.target.value)} required />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          주제
          <input className={FIELD} value={topic} onChange={(e) => setTopic(e.target.value)} required />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          독자층
          <input className={FIELD} value={audience} onChange={(e) => setAudience(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          톤
          <input className={FIELD} value={tone} onChange={(e) => setTone(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          챕터 수: {nChapters}
          <input
            type="range" min={3} max={15} value={nChapters}
            onChange={(e) => setNChapters(Number(e.target.value))}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          목표 분량(단어): {lengthTarget}
          <input
            type="range" min={2000} max={40000} step={1000} value={lengthTarget}
            onChange={(e) => setLengthTarget(Number(e.target.value))}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          생성 엔진
          <select className={FIELD} value={provider} onChange={(e) => setProvider(e.target.value)}>
            <option value="stub">stub (오프라인 결정적)</option>
            <option value="anthropic">anthropic (Claude, 키 필요)</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          윤문 모드
          <select className={FIELD} value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="rules">rules (결정적 무손실)</option>
            <option value="agency">agency (7-Agency 토론)</option>
          </select>
        </label>
      </div>
      <button
        type="submit"
        disabled={disabled}
        className="self-start rounded-full bg-zinc-900 px-6 py-2.5 font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
      >
        {disabled ? "생성 중…" : "원클릭 생성"}
      </button>
    </form>
  );
}
