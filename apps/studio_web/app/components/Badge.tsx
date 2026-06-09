export function Badge({
  ok,
  label,
  neutral = false,
}: {
  ok?: boolean;
  label: string;
  neutral?: boolean;
}) {
  const cls = neutral
    ? "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
    : ok
    ? "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300"
    : "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300";
  return (
    <span className={`rounded-full px-3 py-1 text-sm font-medium ${cls}`}>
      {label}
    </span>
  );
}
