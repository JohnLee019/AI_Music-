import {
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { ScoreDetail } from "../api";

interface Props {
  scores: ScoreDetail;
}

const AXES: { key: keyof ScoreDetail; label: string }[] = [
  { key: "region", label: "지역" },
  { key: "type",   label: "유형" },
  { key: "semantic", label: "의미" },
  { key: "tag",    label: "태그" },
];

export default function ScoreRadar({ scores }: Props) {
  const data = AXES.map(({ key, label }) => ({
    axis: label,
    value: Math.round(scores[key] * 100),
  }));

  return (
    <ResponsiveContainer width="100%" height={160}>
      <RadarChart cx="50%" cy="50%" outerRadius="65%" data={data}>
        <PolarGrid stroke="#e7e5e4" />
        <PolarAngleAxis dataKey="axis" tick={{ fontSize: 11, fill: "#78716c" }} />
        <Radar
          name="점수"
          dataKey="value"
          stroke="#4a7c59"
          fill="#4a7c59"
          fillOpacity={0.25}
          dot={{ r: 3, fill: "#4a7c59" }}
        />
        <Tooltip formatter={(v: number) => [`${v}점`, "점수"]} />
      </RadarChart>
    </ResponsiveContainer>
  );
}
