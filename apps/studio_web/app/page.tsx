"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

type PolishResult = {
  ok: boolean;
  reason?: string | null;
  coverage?: { ok: boolean; source: number; polished: number; missing: string[] };
  qa?: { ok: boolean; blocking_failed: string[]; hardfail: { failures: string[]; warnings: string[] } };
  pipeline?: { pages: number; blocks: number; chunks: number; processed_chunks: number };
  polished_markdown?: string;
};

export default function Home() {
  const [title, setTitle] = useState("제로존 표준수학정리집");
  const [mode, setMode] = useState<"rules" | "agency">("rules");
  const [text, setText] = useState(
    "# 1장 서론\n\n제로존 이론은 2026년에 정리되었다.  공백이   많은 문장이다.\n리만 가설은 미해결 문제로 남아 있다.\n"
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PolishResult | null>(null);

  async function runPolish() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/polish`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, title, mode }),
      });
      if (!res.ok) throw new Error(`API ${res.status}`);
      setResult((await res.json()) as PolishResult);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  const badge = (ok: boolean) =>
    ok ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800";

  return (
    <div className="min-h-screen bg-zinc-50 font-sans text-zinc-900 dark:bg-black dark:text-zinc-100">
      <main className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-12">
        <header>
          <h1 className="text-3xl font-semibold tracking-tight">OneClick eBook Studio</h1>
          <p className="mt-1 text-zinc-600 dark:text-zinc-400">
            원장 기반 무손실 윤문 엔진(ebook_polisher v3)에 연결된 원클릭 스튜디오.
          </p>
        </header>

        <section className="flex flex-col gap-4 rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
          <label className="flex flex-col gap-1 text-sm font-medium">
            제목
            <input
              className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>

          <label className="flex flex-col gap-1 text-sm font-medium">
            모드
            <select
              className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
              value={mode}
              onChange={(e) => setMode(e.target.value as "rules" | "agency")}
            >
              <option value="rules">rules (결정적 무손실)</option>
              <option value="agency">agency (7-Agency 토론)</option>
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm font-medium">
            원고 (Markdown/텍스트)
            <textarea
              className="h-56 rounded-md border border-zinc-300 px-3 py-2 font-mono text-sm dark:border-zinc-700 dark:bg-zinc-900"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </label>

          <button
            onClick={runPolish}
            disabled={loading}
            className="self-start rounded-full bg-zinc-900 px-6 py-2.5 font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
          >
            {loading ? "윤문 중…" : "윤문 시작"}
          </button>
        </section>

        {error && (
          <div className="rounded-lg bg-red-50 px-4 py-3 text-red-700 dark:bg-red-950 dark:text-red-300">
            오류: {error} — API 서버(uvicorn, 8000포트)가 실행 중인지 확인하세요.
          </div>
        )}

        {result && (
          <section className="flex flex-col gap-4 rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className={`rounded-full px-3 py-1 font-medium ${badge(result.ok)}`}>
                출판가능: {result.ok ? "예" : "아니오"}
              </span>
              {result.coverage && (
                <span className={`rounded-full px-3 py-1 font-medium ${badge(result.coverage.ok)}`}>
                  커버리지 {result.coverage.polished}/{result.coverage.source}
                </span>
              )}
              {result.qa && (
                <span className={`rounded-full px-3 py-1 font-medium ${badge(result.qa.ok)}`}>
                  QA {result.qa.ok ? "통과" : "차단"}
                </span>
              )}
              {result.pipeline && (
                <span className="rounded-full bg-zinc-100 px-3 py-1 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                  {result.pipeline.pages}p · {result.pipeline.blocks}블록 · {result.pipeline.chunks}청크
                </span>
              )}
            </div>

            {result.qa?.hardfail?.failures?.length ? (
              <div className="rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:bg-amber-950 dark:text-amber-200">
                Hard-Fail 보고: {result.qa.hardfail.failures.join(", ")}
              </div>
            ) : null}

            <div>
              <h2 className="mb-2 text-sm font-semibold text-zinc-500">윤문 결과</h2>
              <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-zinc-50 p-4 text-sm dark:bg-zinc-900">
                {result.polished_markdown}
              </pre>
            </div>
          </section>
        )}

        <footer className="text-center text-xs text-zinc-400">
          OneClick eBook Studio · 엔진: ebook_polisher v3 (page/block ledger, coverage gate, lossless)
        </footer>
      </main>
    </div>
  );
}
