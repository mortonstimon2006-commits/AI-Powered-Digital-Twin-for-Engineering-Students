import { Slider as RSlider, Switch as RSwitch } from "radix-ui";
import { forwardRef, useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const fieldBase =
  "w-full rounded-lg border border-line bg-ink-800/80 px-3 text-sm text-fg placeholder:text-fg-faint transition " +
  "hover:border-line-strong focus:border-aurora/70 focus:outline-none focus:ring-2 focus:ring-aurora/20 " +
  "disabled:cursor-not-allowed disabled:opacity-60 aria-[invalid=true]:border-danger/70 aria-[invalid=true]:ring-danger/20";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...props }, ref) {
  return <input ref={ref} className={cn(fieldBase, "h-10", className)} {...props} />;
});

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea(
  { className, ...props },
  ref,
) {
  return <textarea ref={ref} className={cn(fieldBase, "min-h-24 py-2.5 leading-relaxed", className)} {...props} />;
});

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select(
  { className, children, ...props },
  ref,
) {
  return (
    <select ref={ref} className={cn(fieldBase, "h-10 appearance-none bg-[length:12px] bg-[right_0.75rem_center] bg-no-repeat pr-8", className)}
      style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 12'%3E%3Cpath d='M2 4l4 4 4-4' fill='none' stroke='%23a3b0c6' stroke-width='1.5'/%3E%3C/svg%3E\")" }}
      {...props}
    >
      {children}
    </select>
  );
});

/** Label + control + hint + error, with aria wiring. */
export function Field({
  label,
  hint,
  error,
  children,
  className,
  required,
}: {
  label: ReactNode;
  hint?: ReactNode;
  error?: string;
  children: (ids: { id: string; describedBy: string | undefined; invalid: boolean }) => ReactNode;
  className?: string;
  required?: boolean;
}) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errId = error ? `${id}-err` : undefined;
  return (
    <div className={cn("space-y-1.5", className)}>
      <label htmlFor={id} className="block text-sm font-medium text-fg">
        {label}
        {required && <span className="ml-0.5 text-danger" aria-hidden>*</span>}
      </label>
      {children({ id, describedBy: [hintId, errId].filter(Boolean).join(" ") || undefined, invalid: Boolean(error) })}
      {hint && !error && (
        <p id={hintId} className="text-xs text-fg-faint">
          {hint}
        </p>
      )}
      {error && (
        <p id={errId} role="alert" className="text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

export function Slider({
  value,
  onChange,
  min,
  max,
  step = 1,
  label,
  marks,
  className,
  disabled,
}: {
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step?: number;
  label: string;
  marks?: number[];
  className?: string;
  disabled?: boolean;
}) {
  return (
    <div className={cn("w-full", className)}>
      <RSlider.Root
        className="relative flex h-6 w-full touch-none select-none items-center"
        value={[value]}
        min={min}
        max={max}
        step={step}
        disabled={disabled}
        onValueChange={(v) => onChange(v[0] ?? min)}
        aria-label={label}
      >
        <RSlider.Track className="relative h-1.5 grow overflow-hidden rounded-full bg-white/[0.08]">
          <RSlider.Range className="absolute h-full rounded-full bg-gradient-to-r from-aurora to-iris" />
        </RSlider.Track>
        <RSlider.Thumb
          className="block size-5 rounded-full border-2 border-aurora bg-ink-900 shadow-[var(--shadow-glow)] transition hover:scale-110 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-aurora"
          aria-label={label}
        />
      </RSlider.Root>
      {marks && (
        <div className="mt-1 flex justify-between font-mono text-[0.65rem] text-fg-faint" aria-hidden>
          {marks.map((m) => (
            <span key={m}>{m}</span>
          ))}
        </div>
      )}
    </div>
  );
}

export function Switch({ checked, onCheckedChange, label, disabled }: { checked: boolean; onCheckedChange: (v: boolean) => void; label: string; disabled?: boolean }) {
  return (
    <RSwitch.Root
      checked={checked}
      onCheckedChange={onCheckedChange}
      disabled={disabled}
      aria-label={label}
      className="relative h-6 w-11 shrink-0 rounded-full border border-line-strong bg-ink-700 transition data-[state=checked]:border-aurora/50 data-[state=checked]:bg-aurora/30 disabled:opacity-50"
    >
      <RSwitch.Thumb className="block size-4.5 translate-x-0.5 rounded-full bg-fg-muted shadow transition-transform data-[state=checked]:translate-x-[1.35rem] data-[state=checked]:bg-aurora" />
    </RSwitch.Root>
  );
}
