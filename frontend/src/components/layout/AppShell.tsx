import { useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  BrainCircuit,
  ChartSpline,
  ClipboardCheck,
  Compass,
  FileText,
  FlaskConical,
  Gauge,
  LayoutDashboard,
  LogOut,
  Menu,
  Network,
  Route,
  Settings,
  ShieldCheck,
  Target,
  UserRound,
  X,
} from "lucide-react";
import { motion } from "motion/react";
import { Dialog as RD } from "radix-ui";
import { useState, type ComponentType } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useMe, useMentorStatus } from "@/lib/queries";
import type { Role } from "@/lib/types";
import { cn } from "@/lib/utils";

import { Brand } from "./Brand";

interface NavItem {
  to: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  roles?: Role[];
  end?: boolean;
}

const NAV: { group: string; items: NavItem[] }[] = [
  { group: "Overview", items: [{ to: "/app", label: "Dashboard", icon: LayoutDashboard, end: true }] },
  {
    group: "Digital twin",
    items: [
      { to: "/app/profile", label: "Twin profile", icon: UserRound },
      { to: "/app/progress", label: "Progress", icon: ChartSpline },
    ],
  },
  {
    group: "Intelligence",
    items: [
      { to: "/app/readiness", label: "Readiness", icon: Gauge },
      { to: "/app/roles", label: "Role explorer", icon: Compass },
      { to: "/app/gaps", label: "Skill gaps", icon: Target },
      { to: "/app/simulator", label: "What-if simulator", icon: FlaskConical },
      { to: "/app/graph", label: "Knowledge graph", icon: Network },
    ],
  },
  {
    group: "Plan & guidance",
    items: [
      { to: "/app/roadmap", label: "Roadmap", icon: Route },
      { to: "/app/mentor", label: "AI mentor", icon: Bot },
      { to: "/app/documents", label: "Resume & JD", icon: FileText },
    ],
  },
  {
    group: "Staff",
    items: [
      { to: "/app/staff", label: "Mentor tools", icon: ClipboardCheck, roles: ["mentor", "admin"] },
      { to: "/app/admin", label: "Administration", icon: ShieldCheck, roles: ["admin"] },
    ],
  },
];

function NavList({ role, onNavigate }: { role: Role; onNavigate?: () => void }) {
  return (
    <nav aria-label="Main" className="space-y-6">
      {NAV.map((g) => {
        const items = g.items.filter((i) => !i.roles || i.roles.includes(role));
        if (!items.length) return null;
        return (
          <div key={g.group}>
            <p className="eyebrow mb-2 px-3">{g.group}</p>
            <ul className="space-y-0.5">
              {items.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.end}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      cn(
                        "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                        isActive ? "bg-white/[0.06] text-fg" : "text-fg-muted hover:bg-white/[0.03] hover:text-fg",
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        {isActive && (
                          <motion.span
                            layoutId="nav-active"
                            className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-aurora"
                            transition={{ type: "spring", stiffness: 500, damping: 40 }}
                          />
                        )}
                        <item.icon className={cn("size-4 shrink-0", isActive ? "text-aurora" : "text-fg-faint group-hover:text-fg-muted")} />
                        {item.label}
                      </>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}

function MentorDot() {
  const { data } = useMentorStatus();
  const ok = data?.available;
  return (
    <span className="inline-flex items-center gap-2 text-xs text-fg-muted" title={ok ? "Local mentor online" : "Local mentor unavailable"}>
      <span className={cn("size-2 rounded-full", ok ? "bg-ok shadow-[0_0_8px] shadow-ok/60" : "bg-fg-faint")} />
      {ok ? "Mentor online" : "Mentor offline"}
    </span>
  );
}

export function AppShell() {
  const { data: me } = useMe();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const role = me?.user.role ?? "student";

  async function logout() {
    try {
      await api("/auth/logout", { method: "POST" });
    } finally {
      qc.clear();
      navigate("/login", { replace: true });
      toast.success("Signed out.");
    }
  }

  const userBlock = (
    <div className="space-y-3 border-t border-line pt-4">
      <MentorDot />
      <div className="flex items-center gap-3">
        <div className="grid size-9 shrink-0 place-items-center rounded-full bg-gradient-to-br from-aurora/30 to-iris/30 font-display text-sm font-semibold">
          {me?.user.display_name.slice(0, 1).toUpperCase()}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{me?.user.display_name}</p>
          <p className="truncate text-xs text-fg-faint capitalize">{role}</p>
        </div>
      </div>
      <div className="flex gap-1">
        <Button variant="ghost" size="sm" className="flex-1 justify-start" onClick={() => navigate("/app/settings")}>
          <Settings className="size-4" /> Settings
        </Button>
        <Button variant="ghost" size="sm" onClick={logout} aria-label="Sign out">
          <LogOut className="size-4" />
        </Button>
      </div>
    </div>
  );

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[260px_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-ink-750 focus:px-3 focus:py-2">
        Skip to content
      </a>
      <aside className="sticky top-0 hidden h-dvh flex-col gap-6 overflow-y-auto border-r border-line bg-ink-900/60 px-4 py-5 backdrop-blur-xl lg:flex">
        <div className="px-2">
          <Brand to="/app" />
        </div>
        <div className="flex-1">
          <NavList role={role} />
        </div>
        {userBlock}
      </aside>

      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-ink-900/80 px-4 py-3 backdrop-blur-xl lg:hidden">
        <Brand to="/app" />
        <RD.Root open={open} onOpenChange={setOpen}>
          <RD.Trigger asChild>
            <Button variant="ghost" size="icon" aria-label="Open navigation">
              <Menu className="size-5" />
            </Button>
          </RD.Trigger>
          <RD.Portal>
            <RD.Overlay className="fixed inset-0 z-40 bg-ink-950/70 backdrop-blur-sm" />
            <RD.Content className="fixed inset-y-0 right-0 z-50 flex w-[min(85vw,320px)] flex-col gap-6 overflow-y-auto border-l border-line bg-ink-850 px-4 py-5">
              <div className="flex items-center justify-between">
                <RD.Title className="font-display font-semibold">Navigation</RD.Title>
                <RD.Description className="sr-only">TwinPath sections</RD.Description>
                <RD.Close asChild>
                  <Button variant="ghost" size="icon" aria-label="Close navigation">
                    <X className="size-5" />
                  </Button>
                </RD.Close>
              </div>
              <div className="flex-1">
                <NavList role={role} onNavigate={() => setOpen(false)} />
              </div>
              {userBlock}
            </RD.Content>
          </RD.Portal>
        </RD.Root>
      </header>

      <main id="main" className="min-w-0 px-4 pb-16 pt-6 sm:px-6 lg:px-10 lg:pt-8">
        <motion.div
          key={location.pathname}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto max-w-7xl"
        >
          <Outlet />
        </motion.div>
      </main>
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  icon: Icon = BrainCircuit,
}: {
  eyebrow: string;
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  icon?: ComponentType<{ className?: string }>;
}) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <p className="eyebrow mb-2 flex items-center gap-2">
          <Icon className="size-3.5 text-aurora" /> {eyebrow}
        </p>
        <h1 className="text-2xl font-semibold sm:text-3xl">{title}</h1>
        {description && <p className="mt-2 max-w-2xl text-sm text-fg-muted sm:text-[0.95rem]">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
