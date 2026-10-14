import { Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { Contribution } from "@/lib/types";

export function ShapChart({ contributions, outputSpace, max = 10 }: { contributions: Contribution[]; outputSpace: string; max?: number }) {
  const data = contributions.slice(0, max).map((c) => ({
    name: `${c.label} = ${c.display_value}`,
    value: Number(c.contribution.toFixed(4)),
  })).reverse();
  return (
    <div style={{ height: Math.max(220, data.length * 34) }} role="img"
      aria-label={`Feature attributions in ${outputSpace.replace("_", " ")} units. ${contributions.slice(0, 3).map((c) => `${c.label} ${c.direction} the estimate`).join("; ")}.`}>
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
          <XAxis type="number" tick={{ fill: "#6f7d96", fontSize: 11 }} stroke="#233049" />
          <YAxis type="category" dataKey="name" width={210} tick={{ fill: "#a3b0c6", fontSize: 11 }} stroke="#233049" />
          <ReferenceLine x={0} stroke="#6f7d96" />
          <Tooltip cursor={{ fill: "rgb(255 255 255 / 0.03)" }}
            contentStyle={{ background: "#131b2e", border: "1px solid #31405e", borderRadius: 10, color: "#e8edf6" }}
            formatter={(v) => [`${Number(v) > 0 ? "+" : ""}${v} (${outputSpace.replace("_", "-")})`, "Contribution"]} />
          <Bar dataKey="value" radius={[3, 3, 3, 3]} isAnimationActive>
            {data.map((d) => <Cell key={d.name} fill={d.value >= 0 ? "#34d399" : "#fb7185"} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
