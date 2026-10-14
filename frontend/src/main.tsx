import "@/styles/index.css";

import { QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "motion/react";
import { Tooltip } from "radix-ui";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router";
import { Toaster } from "sonner";

import { queryClient } from "@/lib/queries";
import { router } from "@/router";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <MotionConfig reducedMotion="user">
        <Tooltip.Provider delayDuration={200}>
          <RouterProvider router={router} />
          <Toaster
            theme="dark"
            position="bottom-right"
            toastOptions={{ classNames: { toast: "!bg-ink-750 !border-line-strong !text-fg", description: "!text-fg-muted" } }}
          />
        </Tooltip.Provider>
      </MotionConfig>
    </QueryClientProvider>
  </StrictMode>,
);
