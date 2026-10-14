import { X } from "lucide-react";
import { AlertDialog, Dialog as RD, Tabs as RTabs } from "radix-ui";
import { useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

import { Button } from "./button";

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  wide,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <RD.Root open={open} onOpenChange={onOpenChange}>
      <RD.Portal>
        <RD.Overlay className="fixed inset-0 z-40 bg-ink-950/70 backdrop-blur-sm data-[state=open]:animate-in" />
        <RD.Content
          className={cn(
            "fixed left-1/2 top-1/2 z-50 max-h-[90dvh] w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-2xl border border-line-strong bg-ink-850 p-6 shadow-2xl focus:outline-none",
            wide ? "max-w-3xl" : "max-w-lg",
          )}
        >
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <RD.Title className="text-lg font-semibold">{title}</RD.Title>
              {description ? (
                <RD.Description className="mt-1 text-sm text-fg-muted">{description}</RD.Description>
              ) : (
                <RD.Description className="sr-only">Dialog</RD.Description>
              )}
            </div>
            <RD.Close asChild>
              <Button variant="ghost" size="icon" aria-label="Close dialog">
                <X className="size-4" />
              </Button>
            </RD.Close>
          </div>
          {children}
        </RD.Content>
      </RD.Portal>
    </RD.Root>
  );
}

/** Confirmation for destructive / irreversible actions. */
export function ConfirmButton({
  trigger,
  title,
  description,
  confirmLabel = "Confirm",
  destructive = true,
  onConfirm,
}: {
  trigger: ReactNode;
  title: ReactNode;
  description: ReactNode;
  confirmLabel?: string;
  destructive?: boolean;
  onConfirm: () => Promise<unknown> | void;
}) {
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  return (
    <AlertDialog.Root open={open} onOpenChange={setOpen}>
      <AlertDialog.Trigger asChild>{trigger}</AlertDialog.Trigger>
      <AlertDialog.Portal>
        <AlertDialog.Overlay className="fixed inset-0 z-40 bg-ink-950/70 backdrop-blur-sm" />
        <AlertDialog.Content className="fixed left-1/2 top-1/2 z-50 w-[calc(100vw-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-line-strong bg-ink-850 p-6 shadow-2xl">
          <AlertDialog.Title className="text-lg font-semibold">{title}</AlertDialog.Title>
          <AlertDialog.Description className="mt-2 text-sm text-fg-muted">{description}</AlertDialog.Description>
          <div className="mt-6 flex justify-end gap-2">
            <AlertDialog.Cancel asChild>
              <Button variant="secondary">Cancel</Button>
            </AlertDialog.Cancel>
            <Button
              variant={destructive ? "danger" : "primary"}
              loading={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await onConfirm();
                  setOpen(false);
                } finally {
                  setBusy(false);
                }
              }}
            >
              {confirmLabel}
            </Button>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  );
}

export function Tabs({
  value,
  onValueChange,
  items,
  children,
  className,
}: {
  value: string;
  onValueChange: (v: string) => void;
  items: { value: string; label: ReactNode; count?: number }[];
  children: ReactNode;
  className?: string;
}) {
  return (
    <RTabs.Root value={value} onValueChange={onValueChange} className={className}>
      <RTabs.List className="-mx-1 flex gap-1 overflow-x-auto border-b border-line px-1" aria-label="Sections">
        {items.map((it) => (
          <RTabs.Trigger
            key={it.value}
            value={it.value}
            className="relative -mb-px inline-flex shrink-0 items-center gap-2 border-b-2 border-transparent px-3 py-2.5 text-sm text-fg-muted transition hover:text-fg data-[state=active]:border-aurora data-[state=active]:text-fg"
          >
            {it.label}
            {it.count !== undefined && <span className="rounded-full bg-white/[0.06] px-1.5 font-mono text-[0.65rem]">{it.count}</span>}
          </RTabs.Trigger>
        ))}
      </RTabs.List>
      {children}
    </RTabs.Root>
  );
}

export const TabPanel = RTabs.Content;
