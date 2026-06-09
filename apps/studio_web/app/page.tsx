"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Job, type Project, type ProjectOptions } from "./lib/api";
import { ProjectForm } from "./components/ProjectForm";
import { ProgressTimeline } from "./components/ProgressTimeline";
import { ResultPanel } from "./components/ResultPanel";

export default function Home() {
  const [project, setProject] = useState<Project | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPoll = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const refreshProject = useCallback(async (projectId: string) => {
    const p = await api.getProject(projectId);
    setProject(p);
  }, []);

  async function handleCreate(
    opts: ProjectOptions & { provider: string; mode: string }
  ) {
    setBusy(true);
    setError(null);
    setProject(null);
    setJob(null);
    stopPoll();
    try {
      const created = await api.createProject(opts);
      setProject(created);
      const { job_id } = await api.startCompose(
        created.project_id,
        opts.provider,
        opts.mode
      );
      pollRef.current = setInterval(async () => {
        try {
          const j = await api.getJob(job_id);
          setJob(j);
          if (j.state === "done" || j.state === "failed") {
            stopPoll();
            setBusy(false);
            if (j.state === "done") await refreshProject(created.project_id);
          }
        } catch (e) {
          stopPoll();
          setBusy(false);
          setError(e instanceof Error ? e.message : String(e));
        }
      }, 400);
    } catch (e) {
      setBusy(false);
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => stopPoll, []);

  return (
    <div className="min-h-screen bg-zinc-50 font-sans text-zinc-900 dark:bg-black dark:text-zinc-100">
      <main className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-12">
        <header>
          <h1 className="text-3xl font-semibold tracking-tight">
            OneClick eBook Studio
          </h1>
          <p className="mt-1 text-zinc-600 dark:text-zinc-400">
            제목과 주제만 입력하면 목차 → 집필 → 윤문 → EPUB까지 한 번에. 원장 기반
            무손실 엔진(ebook_polisher v3) + OCES 생성 파이프라인.
          </p>
        </header>

        <ProjectForm onSubmit={handleCreate} disabled={busy} />

        {error && (
          <div className="rounded-lg bg-red-50 px-4 py-3 text-red-700 dark:bg-red-950 dark:text-red-300">
            오류: {error} — API 서버(uvicorn, 8000포트)가 실행 중인지 확인하세요.
          </div>
        )}

        {job && <ProgressTimeline job={job} />}

        {project?.result && (
          <ResultPanel
            project={project}
            onChanged={() => refreshProject(project.project_id)}
          />
        )}

        <footer className="text-center text-xs text-zinc-400">
          OCES · 생성(OUTLINE·WRITE) + 윤문(EDIT·QA) + 출력(EPUB/MD/HTML) ·
          provider-agnostic LLM(Claude 연결 가능)
        </footer>
      </main>
    </div>
  );
}
