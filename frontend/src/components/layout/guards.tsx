import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";

import { LoadingBlock } from "@/components/ui/states";
import { useMe } from "@/lib/queries";
import type { Role } from "@/lib/types";

function Splash() {
  return (
    <div className="mx-auto mt-24 max-w-md px-6">
      <LoadingBlock rows={2} label="Checking your session" />
    </div>
  );
}

export function RequireAuth({ children, roles }: { children: ReactNode; roles?: Role[] }) {
  const { data: me, isLoading } = useMe();
  const location = useLocation();
  if (isLoading) return <Splash />;
  if (!me) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  if (roles && !roles.includes(me.user.role)) return <Navigate to="/app/forbidden" replace />;
  const needsOnboarding = me.user.role === "student" && !me.onboarding_completed;
  const onOnboarding = location.pathname.startsWith("/app/onboarding");
  if (needsOnboarding && !onOnboarding) return <Navigate to="/app/onboarding" replace />;
  if (!needsOnboarding && onOnboarding) return <Navigate to="/app" replace />;
  return <>{children}</>;
}

export function RedirectIfAuthed({ children }: { children: ReactNode }) {
  const { data: me, isLoading } = useMe();
  if (isLoading) return <Splash />;
  if (me) return <Navigate to="/app" replace />;
  return <>{children}</>;
}
