"use client";

import { useEffect, useRef, useState } from "react";
import { api, type Chapter, type Project } from "../lib/api";
import { Badge } from "./Badge";

function ChapterRow({
  projectId,
  chapter,
  onRegenerate,
  onSaved,
  busy,
}: {
  projectId: string;
  chapter: Chapter;
  onRegenerate: (idx: number) => void;
  onSaved: () => void;
  busy: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(chapter.content_md);
  const [saved, setSaved] = useState<"idle" | "saving" | "saved">("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => setText(chapter.content_md), [chapter.content_md]);

  function onChange(v: string) {
    setText(v);
    setSaved("saving");
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      try {
        await api.editChapter(projectId, chapter.idx, v); // 디바운스 자동저장
        setSaved("saved");
        onSaved();
      } catch {
        setSaved("idle");
      }
    }, 800);
  }

  return (
    <li className="py-2">
      <div className="flex items-center justify-between text-sm">
        <button onClick={() => setOpen((o) => !o)} className="text-left hover:underline">
          {open ? "▾" : "▸"} {chapter.idx + 1}. {chapter.title}
        </button>
        <div className="flex items-center gap-2">
          {open && saved !== "idle" && (
            <span className="text-xs text-zinc-400">
              {saved === "saving" ? "저장 중…" : "✓ 저장됨"}
            </span>
          )}
          <button
            onClick={() => onRegenerate(chapter.idx)}
            disabled={busy}
            className="rounded-md px-2 py-1 text-xs text-zinc-600 hover:bg-zinc-100 disabled:opacity-50 dark:text-zinc-300 dark:hover:bg-zinc-800"
          >
            ↻ 재생성
          </button>
        </div>
      </div>
      {open && (
        <textarea
          className="mt-2 h-40 w-full rounded-md border border-zinc-300 p-2 font-mono text-xs dark:border-zinc-700 dark:bg-zinc-900"
          value={text}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
    </li>
  );
}

export function ResultPanel({
  project,
  onChanged,
}: {
  project: Project;
  onChanged: () => void;
}) {
  const result = project.result;
  const [busyIdx, setBusyIdx] = useState<number | null>(null);
  if (!result) return null;

  const files = project.files ?? {};
  const chapters: Chapter[] = project.chapters ?? result.chapters ?? [];

  async function regenerate(idx: number) {
    setBusyIdx(idx);
    try {
      await api.regenerate(project.project_id, idx);
      onChanged();
    } finally {
      setBusyIdx(null);
    }
  }

  return (
    <section className="flex flex-col gap-5 rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex gap-5">
        {files.cover && (
          /* 표지 미리보기(SVG) */
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={api.downloadUrl(project.project_id, "cover")}
            alt="표지"
            className="h-40 w-auto rounded-md border border-zinc-200 dark:border-zinc-800"
          />
        )}
        <div className="flex flex-1 flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge ok={result.ok} label={`출판가능: ${result.ok ? "예" : "아니오"}`} />
            {result.coverage && (
              <Badge
                ok={result.coverage.ok}
                label={`커버리지 ${result.coverage.polished}/${result.coverage.source}`}
              />
            )}
            {result.qa && <Badge ok={result.qa.ok} label={`QA ${result.qa.ok ? "통과" : "차단"}`} />}
            {result.pipeline && (
              <Badge
                neutral
                label={`${result.pipeline.pages}p · ${result.pipeline.blocks}블록`}
              />
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            {(["epub", "pdf", "docx", "md", "html"] as const).map((fmt) =>
              files[fmt] ? (
                <a
                  key={fmt}
                  href={api.downloadUrl(project.project_id, fmt)}
                  className="rounded-full border border-zinc-300 px-4 py-1.5 text-sm font-medium hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
                >
                  ⬇ {fmt.toUpperCase()}
                </a>
              ) : null
            )}
          </div>
        </div>
      </div>

      {result.qa?.hardfail?.failures?.length ? (
        <div className="rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:bg-amber-950 dark:text-amber-200">
          Hard-Fail 보고: {result.qa.hardfail.failures.join(", ")}
        </div>
      ) : null}

      {/* 목차 + 챕터 인라인 편집/재생성 */}
      <div>
        <h3 className="mb-2 text-sm font-semibold text-zinc-500">
          목차 · 챕터 편집 (펼쳐서 직접 수정하면 자동저장)
        </h3>
        <ul className="flex flex-col divide-y divide-zinc-100 dark:divide-zinc-800">
          {chapters.map((c) => (
            <ChapterRow
              key={c.idx}
              projectId={project.project_id}
              chapter={c}
              busy={busyIdx !== null}
              onRegenerate={regenerate}
              onSaved={onChanged}
            />
          ))}
        </ul>
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold text-zinc-500">윤문본 미리보기</h3>
        <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-zinc-50 p-4 text-sm dark:bg-zinc-900">
          {result.polished_markdown}
        </pre>
      </div>
    </section>
  );
}
