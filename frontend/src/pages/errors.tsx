import { Compass, ShieldOff, TriangleAlert } from "lucide-react";
import { isRouteErrorResponse, Link, useRouteError } from "react-router";

import { Brand } from "@/components/layout/Brand";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/states";

function Frame({ standalone, children }: { standalone?: boolean; children: React.ReactNode }) {
  if (!standalone) return <div className="pt-10">{children}</div>;
  return (
    <div className="mx-auto flex min-h-dvh max-w-xl flex-col justify-center gap-8 px-6">
      <Brand />
      {children}
    </div>
  );
}

export function NotFoundPage({ standalone }: { standalone?: boolean }) {
  return (
    <Frame standalone={standalone}>
      <EmptyState
        icon={<Compass className="size-5" />}
        title="This page does not exist"
        action={
          <Button asChild variant="secondary">
            <Link to={standalone ? "/" : "/app"}>Go back</Link>
          </Button>
        }
      >
        The link may be outdated, or the page has moved.
      </EmptyState>
    </Frame>
  );
}

export function ForbiddenPage() {
  return (
    <Frame>
      <EmptyState icon={<ShieldOff className="size-5" />} title="You don't have access to this area"
        action={<Button asChild variant="secondary"><Link to="/app">Back to dashboard</Link></Button>}>
        This section is limited to mentors or administrators.
      </EmptyState>
    </Frame>
  );
}

export function RouteErrorPage() {
  const error = useRouteError();
  const message = isRouteErrorResponse(error) ? `${error.status} ${error.statusText}` : "An unexpected error occurred while rendering this page.";
  return (
    <Frame standalone>
      <EmptyState icon={<TriangleAlert className="size-5" />} title="Something broke on this screen"
        action={<Button onClick={() => window.location.reload()}>Reload</Button>}>
        {message} Your data is safe; reloading usually fixes this.
      </EmptyState>
    </Frame>
  );
}
