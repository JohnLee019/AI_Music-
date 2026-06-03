interface Props {
  label: string;
  value: number;
  color?: string;
}

export default function ScoreBar({ label, value, color = "bg-jade" }: Props) {
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-12 text-stone-500 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-stone-200 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-7 text-right text-stone-400">{pct}%</span>
    </div>
  );
}
