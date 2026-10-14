import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Tooltip } from "recharts";

import { CATEGORY_LABEL } from "@/lib/utils";

import type { TwinAxis } from "../three/TwinCore";

/** 2D equivalent of the 3D twin core (also used as the reduced-motion fallback). */
export function CategoryRadar({ axes, height = 300 }: { axes: TwinAxis[]; height?: number }) {
  const data = axes.map((a) => ({
    category: CATEGORY_LABEL[a.category] ?? a.category,
    you: a.level ?? 0,
    known: a.level !== null,
    required: a.required ?? 0,
  }));
  return (
    <div style={{ height }} role="img" aria-label="Radar chart of your category levels versus target-role requirements">
      <ResponsiveContainer>
        <RadarChart data={data} outerRadius="72%">
          <PolarGrid stroke="#233049" />
          <PolarAngleAxis dataKey="category" tick={{ fill: "#a3b0c6", fontSize: 11 }} />
          <PolarRadiusAxis domain={[0, 4]} tickCount={5} tick={{ fill: "#6f7d96", fontSize: 10 }} axisLine={false} />
          <Radar name="Target requirement" dataKey="required" stroke="#e8edf6" strokeDasharray="4 4" fill="#e8edf6" fillOpacity={0.04} />
          <Radar name="Your level" dataKey="you" stroke="#5eead4" fill="#5eead4" fillOpacity={0.22} />
          <Tooltip
            contentStyle={{ background: "#131b2e", border: "1px solid #31405e", borderRadius: 10, color: "#e8edf6" }}
            formatter={(v, name, item) => {
              const row = item?.payload as { known: boolean } | undefined;
              if (name === "Your level" && row && !row.known) return ["unknown", name];
              return [Number(v).toFixed(1), name];
            }}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
