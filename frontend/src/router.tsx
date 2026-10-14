import { lazy, Suspense, type ComponentType, type ReactNode } from "react";
import { createBrowserRouter, Outlet } from "react-router";

import { AppShell } from "@/components/layout/AppShell";
import { RedirectIfAuthed, RequireAuth } from "@/components/layout/guards";
import { LoadingBlock } from "@/components/ui/states";
import { ForbiddenPage, NotFoundPage, RouteErrorPage } from "@/pages/errors";

function lazyPage(loader: () => Promise<object>, name: string) {
  const Comp = lazy(async () => ({ default: (await loader() as Record<string, ComponentType>)[name]! }));
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-5xl pt-4">
          <LoadingBlock rows={3} />
        </div>
      }
    >
      <Comp />
    </Suspense>
  );
}

const page = {
  landing: () => lazyPage(() => import("@/pages/landing/LandingPage"), "LandingPage"),
  login: () => lazyPage(() => import("@/pages/auth/AuthPages"), "LoginPage"),
  register: () => lazyPage(() => import("@/pages/auth/AuthPages"), "RegisterPage"),
  forgot: () => lazyPage(() => import("@/pages/auth/AuthPages"), "ForgotPasswordPage"),
  reset: () => lazyPage(() => import("@/pages/auth/AuthPages"), "ResetPasswordPage"),
  verify: () => lazyPage(() => import("@/pages/auth/AuthPages"), "VerifyEmailPage"),
  onboarding: () => lazyPage(() => import("@/pages/onboarding/OnboardingPage"), "OnboardingPage"),
  dashboard: () => lazyPage(() => import("@/pages/dashboard/DashboardPage"), "DashboardPage"),
  profile: () => lazyPage(() => import("@/pages/twin/ProfilePage"), "ProfilePage"),
  progress: () => lazyPage(() => import("@/pages/progress/ProgressPage"), "ProgressPage"),
  readiness: () => lazyPage(() => import("@/pages/readiness/ReadinessPage"), "ReadinessPage"),
  modelCard: () => lazyPage(() => import("@/pages/readiness/ModelCardPage"), "ModelCardPage"),
  roles: () => lazyPage(() => import("@/pages/roles/RolesPage"), "RolesPage"),
  gaps: () => lazyPage(() => import("@/pages/gaps/SkillGapsPage"), "SkillGapsPage"),
  simulator: () => lazyPage(() => import("@/pages/simulator/SimulatorPage"), "SimulatorPage"),
  graph: () => lazyPage(() => import("@/pages/graph/GraphPage"), "GraphPage"),
  roadmap: () => lazyPage(() => import("@/pages/roadmap/RoadmapPage"), "RoadmapPage"),
  mentor: () => lazyPage(() => import("@/pages/mentor/MentorPage"), "MentorPage"),
  documents: () => lazyPage(() => import("@/pages/documents/DocumentsPage"), "DocumentsPage"),
  settings: () => lazyPage(() => import("@/pages/settings/SettingsPage"), "SettingsPage"),
  staff: () => lazyPage(() => import("@/pages/staff/StaffPage"), "StaffPage"),
  admin: () => lazyPage(() => import("@/pages/admin/AdminPage"), "AdminPage"),
};

const guest = (node: ReactNode) => <RedirectIfAuthed>{node}</RedirectIfAuthed>;

export const router = createBrowserRouter([
  {
    errorElement: <RouteErrorPage />,
    children: [
      { path: "/", element: page.landing() },
      { path: "/login", element: guest(page.login()) },
      { path: "/register", element: guest(page.register()) },
      { path: "/forgot-password", element: guest(page.forgot()) },
      { path: "/reset-password", element: page.reset() },
      { path: "/verify-email", element: page.verify() },
      {
        path: "/app/onboarding",
        element: (
          <RequireAuth>
            <div className="min-h-dvh px-4 py-8 sm:px-6">{page.onboarding()}</div>
          </RequireAuth>
        ),
      },
      {
        path: "/app",
        element: (
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        ),
        children: [
          { index: true, element: page.dashboard() },
          { path: "profile", element: page.profile() },
          { path: "progress", element: page.progress() },
          { path: "readiness", element: page.readiness() },
          { path: "readiness/model", element: page.modelCard() },
          { path: "roles", element: page.roles() },
          { path: "gaps", element: page.gaps() },
          { path: "simulator", element: page.simulator() },
          { path: "graph", element: page.graph() },
          { path: "roadmap", element: page.roadmap() },
          { path: "mentor", element: page.mentor() },
          { path: "documents", element: page.documents() },
          { path: "settings", element: page.settings() },
          {
            path: "staff",
            element: (
              <RequireAuth roles={["mentor", "admin"]}>
                <Outlet />
              </RequireAuth>
            ),
            children: [{ index: true, element: page.staff() }],
          },
          {
            path: "admin",
            element: (
              <RequireAuth roles={["admin"]}>
                <Outlet />
              </RequireAuth>
            ),
            children: [{ index: true, element: page.admin() }],
          },
          { path: "forbidden", element: <ForbiddenPage /> },
          { path: "*", element: <NotFoundPage /> },
        ],
      },
      { path: "*", element: <NotFoundPage standalone /> },
    ],
  },
]);
