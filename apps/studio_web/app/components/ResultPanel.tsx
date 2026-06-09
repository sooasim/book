"use client";

import { useState } from "react";
import { api, type Project } from "../lib/api";
import { Badge } from "./Badge";

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
            label={`${result.pipeline.pages}p · ${result.pipeline.blocks}블록 · ${result.pipeline.chunks}청크`}
          />
        )}
      </div>

      {result.qa?.hardfail?.failures?.length ? (
        <div className="rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:bg-amber-950 dark:text-amber-200">
          Hard-Fail 보고: {result.qa.hardfail.failures.join(", ")}
        </div>
      ) : null}

      {/* 다운로드 */}
      <div className="flex flex-wrap gap-2">
        {(["epub", "md", "html", "pdf", "docx"] as const).map((fmt) =>
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

      {/* 목차 + 챕터 재생성 */}
      <div>
        <h3 className="mb-2 text-sm font-semibold text-zinc-500">목차</h3>
        <ul className="flex flex-col divide-y divide-zinc-100 dark:divide-zinc-800">
          {(project.outline ?? result.outline ?? []).map((c) => (
            <li key={c.idx} className="flex items-center justify-between py-2 text-sm">
              <span>
                {c.idx + 1}. {c.title}{" "}
                <span className="text-zinc-400">({c.target_words}단어)</span>
              </span>
              <button
                onClick={() => regenerate(c.idx)}
                disabled={busyIdx !== null}
                className="rounded-md px-2 py-1 text-xs text-zinc-600 hover:bg-zinc-100 disabled:opacity-50 dark:text-zinc-300 dark:hover:bg-zinc-800"
              >
                {busyIdx === c.idx ? "재생성 중…" : "↻ 재생성"}
              </button>
            </li>
          ))}
        </ul>
      </div>

      {/* 윤문본 미리보기 */}
      <div>
        <h3 className="mb-2 text-sm font-semibold text-zinc-500">윤문본 미리보기</h3>
        <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-zinc-50 p-4 text-sm dark:bg-zinc-900">
          {result.polished_markdown}
        </pre>
      </div>
    </section>
  );
}
