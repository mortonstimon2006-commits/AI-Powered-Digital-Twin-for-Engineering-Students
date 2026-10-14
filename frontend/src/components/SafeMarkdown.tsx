import { Fragment, type ReactNode } from "react";

/**
 * Minimal, XSS-safe markdown subset for model output: paragraphs, "-"/"*"/"1." lists,
 * **bold**, `code`, and [S1]-style citations. Everything is rendered as React text nodes —
 * no HTML is ever interpreted.
 */
function inline(text: string, onCite?: (ref: string) => void): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\[S\d{1,2}\]|\[[^\]\n]{1,200}\]\(https:\/\/[^)\s]{1,500}\))/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let k = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) out.push(<strong key={k++} className="font-semibold text-fg">{tok.slice(2, -2)}</strong>);
    else if (tok.startsWith("`")) out.push(<code key={k++} className="rounded bg-ink-700 px-1 py-0.5 font-mono text-[0.85em]">{tok.slice(1, -1)}</code>);
    else if (tok.includes("](https://")) {
      // Only https links survive server-side sanitisation (verified catalogue URLs). React escapes
      // the attribute, and the https:// prefix rules out javascript:/data: URLs.
      const label = tok.slice(1, tok.indexOf("]("));
      const href = tok.slice(tok.indexOf("](") + 2, -1);
      out.push(
        <a key={k++} href={href} target="_blank" rel="noopener noreferrer nofollow" className="text-aurora underline-offset-2 hover:underline">
          {label}
        </a>,
      );
    } else {
      const ref = tok.slice(1, -1);
      out.push(
        <button key={k++} type="button" onClick={() => onCite?.(ref)}
          className="mx-0.5 inline-flex rounded bg-aurora/15 px-1 font-mono text-[0.72em] text-aurora align-[1px] hover:bg-aurora/25" aria-label={`Source ${ref}`}>
          {ref}
        </button>,
      );
    }
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export function SafeMarkdown({ text, onCite }: { text: string; onCite?: (ref: string) => void }) {
  const blocks = text.replace(/\r\n/g, "\n").split(/\n{2,}/);
  return (
    <div className="space-y-2.5 text-sm leading-relaxed text-fg/90">
      {blocks.map((block, i) => {
        const lines = block.split("\n").filter((l) => l.trim());
        if (!lines.length) return null;
        const isList = lines.every((l) => /^\s*([-*•]|\d+[.)])\s+/.test(l));
        if (isList) {
          const ordered = /^\s*\d+[.)]/.test(lines[0]!);
          const items = lines.map((l) => l.replace(/^\s*([-*•]|\d+[.)])\s+/, ""));
          const List = ordered ? "ol" : "ul";
          return (
            <List key={i} className={ordered ? "list-decimal space-y-1 pl-5" : "list-disc space-y-1 pl-5 marker:text-aurora"}>
              {items.map((it, j) => <li key={j}>{inline(it, onCite)}</li>)}
            </List>
          );
        }
        const heading = lines[0]!.match(/^#{1,4}\s+(.*)/);
        return (
          <p key={i}>
            {heading ? <strong className="block font-display text-fg">{heading[1]}</strong> : null}
            {(heading ? lines.slice(1) : lines).map((l, j) => <Fragment key={j}>{j > 0 && <br />}{inline(l, onCite)}</Fragment>)}
          </p>
        );
      })}
    </div>
  );
}
