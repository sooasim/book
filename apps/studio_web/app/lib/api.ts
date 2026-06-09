// OneClick eBook Studio — API 클라이언트 (typed)
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export type ProjectOptions = {
  title: string;
  topic: string;
  author?: string;
  audience?: string;
  tone?: string;
  language?: string;
  length_target?: number;
  n_chapters?: number;
};

export type Project = {
  project_id: string;
  title: string;
  topic: string;
  status: string;
  outline?: OutlineChapter[];
  chapters?: Chapter[];
  files?: Record<string, string>;
  result?: ComposeResult | null;
};

export type OutlineChapter = {
  idx: number;
  title: string;
  brief: string;
  target_words: number;
};

export type Chapter = {
  idx: number;
  title: string;
  content_md: string;
  summary: string;
};

export type JobEvent = {
  ts: string;
  stage: string;
  level: string;
  message: string;
  payload?: Record<string, unknown> | null;
};

export type Job = {
  id: string;
  project_id: string;
  state: "queued" | "running" | "done" | "failed" | "paused";
  current_stage: string;
  progress: number;
  events: JobEvent[];
  error?: Record<string, unknown> | null;
};

export type ComposeResult = {
  ok: boolean;
  title: string;
  topic: string;
  outline: OutlineChapter[];
  chapters: Chapter[];
  polished_markdown: string;
  coverage?: { ok: boolean; source: number; polished: number };
  qa?: {
    ok: boolean;
    blocking_failed: string[];
    hardfail: { failures: string[]; warnings: string[] };
  };
  pipeline?: { pages: number; blocks: number; chunks: number };
  files?: Record<string, string>;
};

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`API ${res.status} ${path} ${detail}`);
  }
  return (await res.json()) as T;
}

export const api = {
  health: () => jsonFetch<{ ok: boolean; engine: string }>("/health"),

  createProject: (opts: ProjectOptions) =>
    jsonFetch<Project>("/api/projects", {
      method: "POST",
      body: JSON.stringify(opts),
    }),

  startCompose: (projectId: string, provider = "stub", mode = "rules") =>
    jsonFetch<{ job_id: string }>(`/api/projects/${projectId}/compose`, {
      method: "POST",
      body: JSON.stringify({ provider, mode }),
    }),

  getJob: (jobId: string) => jsonFetch<Job>(`/api/jobs/${jobId}`),

  getProject: (projectId: string) =>
    jsonFetch<Project>(`/api/projects/${projectId}`),

  regenerate: (projectId: string, idx: number, provider = "stub", mode = "rules") =>
    jsonFetch<{ ok: boolean; idx: number; content_md: string }>(
      "/api/chapters/regenerate",
      {
        method: "POST",
        body: JSON.stringify({ project_id: projectId, idx, provider, mode }),
      }
    ),

  editChapter: (projectId: string, idx: number, content_md: string) =>
    jsonFetch<{ ok: boolean; idx: number }>("/api/chapters", {
      method: "PATCH",
      body: JSON.stringify({ project_id: projectId, idx, content_md }),
    }),

  pauseJob: (jobId: string) =>
    jsonFetch<{ state: string }>(`/api/jobs/${jobId}/pause`, { method: "POST" }),

  resumeJob: (jobId: string) =>
    jsonFetch<{ status: string }>(`/api/jobs/${jobId}/resume`, { method: "POST" }),

  getUsage: () => jsonFetch<{ tokens: number; books: number; quota: number }>("/api/usage"),

  addSource: (projectId: string, source_id: string, text: string) =>
    jsonFetch<{ sources: number }>(`/api/projects/${projectId}/sources`, {
      method: "POST",
      body: JSON.stringify({ source_id, text }),
    }),

  // 동기 풀 파이프라인(빠른 데모용)
  composeBook: (opts: ProjectOptions & { provider?: string; mode?: string }) =>
    jsonFetch<ComposeResult>("/api/compose/book", {
      method: "POST",
      body: JSON.stringify(opts),
    }),

  downloadUrl: (projectId: string, fmt: string) =>
    `${API_BASE}/api/projects/${projectId}/download/${fmt}`,
};
