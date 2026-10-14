import { useReducedMotion } from "motion/react";
import { lazy, Suspense, useMemo } from "react";

import { CategoryRadar } from "@/components/charts/CategoryRadar";
import type { TwinAxis } from "@/components/three/TwinCore";
import { Skeleton } from "@/components/ui/states";
import type { FeatureRow, Gap } from "@/lib/types";
import { useCan3D } from "@/lib/visuals";

const TwinCore = lazy(() => import("@/components/three/TwinCore"));
const CATS = ["programming", "dsa", "databases", "web", "ml_ai", "data", "cloud_devops", "security"];

export function useTwinAxes(features: FeatureRow[] | undefined, gaps: Gap[] | undefined): TwinAxis[] {
  return useMemo(
    () =>
      CATS.map((cat) => {
        const f = features?.find((x) => x.name === `lvl_${cat}`);
        const reqs = (gaps ?? []).filter((g) => g.category === cat).map((g) => g.required_level);
        return { category: cat, level: f?.value ?? null, required: reqs.length ? Math.max(...reqs) : null };
      }),
    [features, gaps],
  );
}

export function TwinVisual({ axes, height = 320 }: { axes: TwinAxis[]; height?: number }) {
  const { enabled, reason } = useCan3D();
  const reduce = useReducedMotion();
  return (
    <div>
      <div style={{ height }} className="overflow-hidden rounded-xl">
        {enabled ? (
          <Suspense fallback={<Skeleton className="h-full w-full" />}>
            <TwinCore axes={axes} animate={!reduce} />
          </Suspense>
        ) : (
          <CategoryRadar axes={axes} height={height} />
        )}
      </div>
      <p className="mt-2 text-[0.7rem] text-fg-faint">
        {enabled
          ? "Drag to rotate. Spheres show your evidence-weighted level per category; rings mark your target role's highest requirement. Wireframe = unknown."
          : `${reason ?? ""} Showing the 2D chart.`}
      </p>
    </div>
  );
}
