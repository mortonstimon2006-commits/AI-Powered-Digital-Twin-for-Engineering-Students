import { Slot } from "radix-ui";
import { Loader2 } from "lucide-react";
import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const VARIANTS = {
  primary:
    "bg-gradient-to-r from-aurora to-[#7ee8fa] text-ink-950 font-semibold shadow-[var(--shadow-glow)] hover:brightness-110 active:brightness-95",
  secondary: "bg-ink-700 text-fg border border-line-strong hover:bg-ink-750 hover:border-fg-faint/40",
  outline: "border border-line-strong text-fg hover:border-aurora/60 hover:text-aurora bg-transparent",
  ghost: "text-fg-muted hover:text-fg hover:bg-white/[0.04]",
  danger: "bg-danger/90 text-ink-950 font-semibold hover:bg-danger",
  subtle: "bg-aurora/10 text-aurora border border-aurora/20 hover:bg-aurora/15",
} as const;

const SIZES = {
  sm: "h-8 px-3 text-sm gap-1.5 rounded-md",
  md: "h-10 px-4 text-sm gap-2 rounded-lg",
  lg: "h-12 px-6 text-base gap-2.5 rounded-xl",
  icon: "h-9 w-9 rounded-lg justify-center",
} as const;

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof VARIANTS;
  size?: keyof typeof SIZES;
  loading?: boolean;
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant = "primary", size = "md", loading = false, asChild = false, disabled, children, type, ...props },
  ref,
) {
  const Comp = asChild ? Slot.Root : "button";
  return (
    <Comp
      ref={ref}
      type={asChild ? undefined : (type ?? "button")}
      className={cn(
        "inline-flex select-none items-center justify-center whitespace-nowrap font-medium transition-all duration-200",
        "disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-aurora",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {asChild ? (
        children
      ) : (
        <>
          {loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
          {children}
        </>
      )}
    </Comp>
  );
});
