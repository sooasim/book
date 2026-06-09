import type { Job } from "../lib/api";

const STAGE_LABEL: Record<string, string> = {
  outline: "목차 설계",
  write: "본문 집필",
  edit: "교정·윤문",
  factqa: "품질 검사",
  export: "조판·출력",
};

export function ProgressTimeline({ job }: { job: Job }) {
  const stages = ["outline", "write", "edit", "export"];
  const doneStages = new Set(
    job.events
      .filter((e) => e.message === "stage_done")
      .map((e) => e.stage)
  );
  const pct = Math.round((job.progress ?? 0) * 100);

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-center justify-between text-sm">
        <span className="font-semibold">진행 상황</span>
        <span className="text-zinc-500">
          {job.state} · {pct}%
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
        <div
          className="h-full bg-zinc-900 transition-all dark:bg-white"
          style={{ width: `${pct}%` }}
        />
      </div>
      <ol className="flex flex-wrap gap-2">
        {stages.map((s) => {
          const done = doneStages.has(s);
          const active = job.current_stage === s && job.state === "running";
          return (
            <li
              key={s}
              className={`rounded-full px-3 py-1 text-sm ${
                done
                  ? "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300"
                  : active
                  ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200"
                  : "bg-zinc-100 text-zinc-500 dark:bg-zinc-800"
              }`}
            >
              {done ? "✓ " : active ? "● " : "○ "}
              {STAGE_LABEL[s] ?? s}
            </li>
          );
        })}
      </ol>
      {job.state === "failed" && (
        <p className="text-sm text-red-600">
          실패: {String(job.error?.message ?? "알 수 없는 오류")}
        </p>
      )}
    </div>
  );
}
