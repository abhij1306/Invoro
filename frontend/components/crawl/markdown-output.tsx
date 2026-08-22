'use client';

import { Copy } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import katex from 'katex';
import type { KatexOptions } from 'katex';

import { DataRegionEmpty, DataRegionLoading } from '../ui/patterns';
import { Button } from '../ui/primitives';

type KaTeXApi = {
  render: (math: string, element: HTMLElement, options: KatexOptions) => void;
};

type WindowWithKaTeX = Window & { katex?: KaTeXApi };

function loadKaTeX(): Promise<KaTeXApi> {
  if (typeof window === 'undefined') return Promise.reject(new Error('Window is undefined'));
  const browserWindow = window as WindowWithKaTeX;
  if (browserWindow.katex) return Promise.resolve(browserWindow.katex);
  browserWindow.katex = katex;
  return Promise.resolve(katex);
}

export function MathRenderer({
  math,
  displayMode,
}: Readonly<{ math: string; displayMode?: boolean }>) {
  const containerRef = useRef<HTMLSpanElement>(null);
  const katexRef = useRef<KaTeXApi | null>(null);

  useEffect(() => {
    let active = true;
    function renderMath(kt: KaTeXApi | null) {
      if (!containerRef.current) {
        return;
      }
      if (!kt) {
        containerRef.current.textContent = displayMode ? `$$\n${math}\n$$` : `$${math}$`;
        return;
      }
      try {
        kt.render(math, containerRef.current, {
          displayMode: !!displayMode,
          throwOnError: false,
          strict: 'ignore',
        });
      } catch {
        containerRef.current.textContent = math;
      }
    }

    renderMath(katexRef.current);
    loadKaTeX()
      .then((kt) => {
        if (active) {
          katexRef.current = kt;
          renderMath(kt);
        }
      })
      .catch((err) => console.error(err));
    return () => {
      active = false;
    };
  }, [math, displayMode]);

  return (
    <span
      ref={containerRef}
      className={displayMode ? 'block w-full overflow-x-auto py-1 text-center' : 'inline'}
    />
  );
}

function parseInlineMarkdownNodes(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern =
    /(\$\$[\s\S]+?\$\$|\$[^$\n]+\$|`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|_[^_]+_|\[[^\]]+\]\((?:https?:\/\/|\/|#)[^)]+\))/g;
  let cursor = 0;
  for (const match of text.matchAll(pattern)) {
    const index = match.index ?? 0;
    if (index > cursor) {
      nodes.push(text.slice(cursor, index));
    }
    const token = match[0];
    const key = `${index}-${token}`;

    nodes.push(renderInlineToken(token, key));
    cursor = index + token.length;
  }
  if (cursor < text.length) {
    nodes.push(text.slice(cursor));
  }
  return nodes;
}

function renderInlineToken(token: string, key: string): ReactNode {
  if (/^\$\$[\s\S]*\$\$$/.test(token))
    return <MathRenderer key={key} math={token.slice(2, -2)} displayMode />;
  if (/^\$[^$\n]+\$$/.test(token)) return <MathRenderer key={key} math={token.slice(1, -1)} />;
  if (/^`[^`]+`$/.test(token))
    return (
      <code key={key} className="bg-background-alt rounded-sm px-1 py-0.5 font-mono text-[0.92em]">
        {token.slice(1, -1)}
      </code>
    );
  if (/^\*\*[^*]+\*\*$/.test(token)) return <strong key={key}>{token.slice(2, -2)}</strong>;
  if (/^(?:\*[^*]+\*|_[^_]+_)$/.test(token)) return <em key={key}>{token.slice(1, -1)}</em>;
  const link = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
  if (!link) return token;
  const external = !link[2].startsWith('#');
  return (
    <a
      key={key}
      href={link[2]}
      target={external ? '_blank' : undefined}
      rel={external ? 'noreferrer' : undefined}
      className="link-accent underline-offset-2 hover:underline"
    >
      {link[1]}
    </a>
  );
}

function InlineMarkdown({ text }: Readonly<{ text: string }>) {
  return <>{parseInlineMarkdownNodes(text)}</>;
}

function parseTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => cell.trim());
}

function isTableDivider(line: string): boolean {
  const cells = parseTableRow(line);
  return cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/.test(cell));
}

type MarkdownCursor = { lines: string[]; index: number; sequence: number };

function MarkdownPreview({ markdown }: Readonly<{ markdown: string }>) {
  const cursor: MarkdownCursor = {
    lines: markdown.replace(/\r\n/g, '\n').split('\n'),
    index: 0,
    sequence: 0,
  };
  const blocks: ReactNode[] = [];
  while (cursor.index < cursor.lines.length) {
    if (!cursor.lines[cursor.index].trim()) {
      cursor.index += 1;
      continue;
    }
    blocks.push(parseMarkdownBlock(cursor));
  }
  return <div className="px-3 py-5">{blocks}</div>;
}

function nextBlockKey(cursor: MarkdownCursor, prefix: string) {
  cursor.sequence += 1;
  return prefix + '-' + cursor.sequence;
}

function parseMarkdownBlock(cursor: MarkdownCursor): ReactNode {
  const trimmed = cursor.lines[cursor.index].trim();
  if (isFrontmatterStart(cursor, trimmed)) return parseFrontmatterBlock(cursor);
  if (trimmed.startsWith('```')) return parseCodeBlock(cursor, trimmed);
  if (isTableStart(cursor, trimmed)) return parseTableBlock(cursor, trimmed);
  if (trimmed.startsWith('$$')) return parseMathBlock(cursor, trimmed);
  const heading = trimmed.match(/^(#{1,6})\s+(.+)$/);
  if (heading) return parseHeadingBlock(cursor, heading);
  if (/^[-*_]{3,}$/.test(trimmed)) return parseRuleBlock(cursor);
  if (trimmed.startsWith('>')) return parseQuoteBlock(cursor);
  if (/^(?:[-*]\s+|\d+\.\s+)/.test(trimmed)) return parseListBlock(cursor, trimmed);
  return parseParagraphBlock(cursor);
}

function isFrontmatterStart(cursor: MarkdownCursor, trimmed: string) {
  if (cursor.index !== 0 || trimmed !== '---') return false;
  return cursor.lines.slice(1).some((line) => line.trim() === '---');
}

function parseFrontmatterBlock(cursor: MarkdownCursor) {
  const lines: string[] = [];
  cursor.index += 1;
  while (cursor.index < cursor.lines.length && cursor.lines[cursor.index].trim() !== '---') {
    lines.push(cursor.lines[cursor.index]);
    cursor.index += 1;
  }
  cursor.index += 1;
  return (
    <section
      key="frontmatter"
      className="border-border bg-background-alt/60 my-3 overflow-hidden rounded-md border"
    >
      <div className="border-border bg-panel flex items-center justify-between border-b px-4 py-2">
        <div className="type-label text-secondary">Design Tokens</div>
        <div className="text-secondary font-mono text-xs">YAML</div>
      </div>
      <pre className="px-4 py-3 text-xs leading-relaxed whitespace-pre-wrap">
        <code className="font-mono">{lines.join('\n')}</code>
      </pre>
    </section>
  );
}

function parseCodeBlock(cursor: MarkdownCursor, opening: string) {
  const language = opening.slice(3).trim();
  const code: string[] = [];
  cursor.index += 1;
  while (
    cursor.index < cursor.lines.length &&
    !cursor.lines[cursor.index].trim().startsWith('```') &&
    code.length < 500
  ) {
    code.push(cursor.lines[cursor.index]);
    cursor.index += 1;
  }
  while (cursor.index < cursor.lines.length && !cursor.lines[cursor.index].trim().startsWith('```'))
    cursor.index += 1;
  if (cursor.index < cursor.lines.length) cursor.index += 1;
  return (
    <div key={nextBlockKey(cursor, 'code')} className="my-4 overflow-hidden rounded-md border">
      {language ? (
        <div className="bg-background-alt text-secondary border-b px-4 py-1.5 font-mono text-xs">
          {language}
        </div>
      ) : null}
      <pre className="bg-background-alt overflow-x-auto px-4 py-3 text-sm leading-relaxed whitespace-pre">
        <code className="font-mono">{code.join('\n')}</code>
      </pre>
    </div>
  );
}

function isTableStart(cursor: MarkdownCursor, trimmed: string) {
  return (
    trimmed.startsWith('|') &&
    cursor.index + 1 < cursor.lines.length &&
    isTableDivider(cursor.lines[cursor.index + 1])
  );
}

function parseTableBlock(cursor: MarkdownCursor, opening: string) {
  const headers = parseTableRow(opening);
  const rows: string[][] = [];
  cursor.index += 2;
  while (cursor.index < cursor.lines.length && cursor.lines[cursor.index].trim().startsWith('|')) {
    rows.push(parseTableRow(cursor.lines[cursor.index]));
    cursor.index += 1;
  }
  return (
    <div
      key={nextBlockKey(cursor, 'table')}
      className="border-border my-4 overflow-x-auto rounded-md border"
    >
      <table className="w-full min-w-[560px] border-collapse text-sm">
        <thead className="bg-background-alt text-secondary">
          <tr>
            {headers.map((header) => (
              <th
                key={header}
                className="border-border border-b px-3 py-2 text-left font-mono text-xs font-semibold tracking-wide uppercase"
              >
                <InlineMarkdown text={header} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.join('|')} className="odd:bg-background even:bg-background-alt/40">
              {headers.map((header, cellIndex) => (
                <td
                  key={header}
                  className="border-border/70 text-foreground border-b px-3 py-2 align-top"
                >
                  <InlineMarkdown text={row[cellIndex] || ''} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function parseMathBlock(cursor: MarkdownCursor, opening: string) {
  if (opening.endsWith('$$') && opening.length > 2) {
    cursor.index += 1;
    return (
      <div key={nextBlockKey(cursor, 'math')} className="my-4">
        <MathRenderer math={opening.slice(2, -2)} displayMode />
      </div>
    );
  }
  const lines: string[] = [];
  cursor.index += 1;
  while (
    cursor.index < cursor.lines.length &&
    !cursor.lines[cursor.index].trim().startsWith('$$')
  ) {
    lines.push(cursor.lines[cursor.index]);
    cursor.index += 1;
  }
  cursor.index += 1;
  return (
    <div key={nextBlockKey(cursor, 'math')} className="my-4">
      <MathRenderer math={lines.join('\n')} displayMode />
    </div>
  );
}

function parseHeadingBlock(cursor: MarkdownCursor, heading: RegExpMatchArray) {
  const level = heading[1].length;
  const className = headingClass(level);
  const HeadingTag = ('h' + Math.min(level, 6)) as 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
  cursor.index += 1;
  return (
    <HeadingTag key={nextBlockKey(cursor, 'heading')} className={className}>
      <InlineMarkdown text={heading[2]} />
    </HeadingTag>
  );
}

function headingClass(level: number) {
  if (level === 1) return 'type-title text-foreground mt-1 mb-3';
  if (level === 2) return 'type-section text-foreground mt-6 mb-2';
  return 'type-body text-foreground mt-4 mb-2 font-semibold';
}

function parseRuleBlock(cursor: MarkdownCursor) {
  cursor.index += 1;
  return <hr key={nextBlockKey(cursor, 'hr')} className="border-divider my-6" />;
}

function parseQuoteBlock(cursor: MarkdownCursor) {
  const lines: string[] = [];
  while (cursor.index < cursor.lines.length && cursor.lines[cursor.index].trim().startsWith('>')) {
    lines.push(cursor.lines[cursor.index].trim().replace(/^>\s?/, ''));
    cursor.index += 1;
  }
  return (
    <blockquote
      key={nextBlockKey(cursor, 'quote')}
      className="border-accent/40 text-secondary border-l-2 pl-4 leading-relaxed"
    >
      {lines.map((line, index) => (
        <p key={line + '-' + index} className="type-body my-1">
          <InlineMarkdown text={line} />
        </p>
      ))}
    </blockquote>
  );
}

function parseListBlock(cursor: MarkdownCursor, opening: string) {
  const ordered = /^\d+\.\s+/.test(opening);
  const pattern = ordered ? /^\d+\.\s+(.+)$/ : /^[-*]\s+(.+)$/;
  const items: string[] = [];
  while (cursor.index < cursor.lines.length) {
    const item = cursor.lines[cursor.index].trim().match(pattern);
    if (!item) break;
    items.push(item[1]);
    cursor.index += 1;
  }
  const ListTag: 'ol' | 'ul' = ordered ? 'ol' : 'ul';
  return (
    <ListTag
      key={nextBlockKey(cursor, 'list')}
      className="type-body text-foreground my-3 space-y-1 pl-6 leading-relaxed"
    >
      {items.map((item, index) => (
        <li key={item + '-' + index} className={ordered ? 'list-decimal' : 'list-disc'}>
          <InlineMarkdown text={item} />
        </li>
      ))}
    </ListTag>
  );
}

function parseParagraphBlock(cursor: MarkdownCursor) {
  const lines: string[] = [];
  while (cursor.index < cursor.lines.length && !startsMarkdownBlock(cursor)) {
    lines.push(cursor.lines[cursor.index].trim());
    cursor.index += 1;
  }
  if (!lines.length && cursor.index < cursor.lines.length) {
    lines.push(cursor.lines[cursor.index].trim());
    cursor.index += 1;
  }
  return (
    <p key={nextBlockKey(cursor, 'p')} className="type-body text-foreground my-3 leading-[1.72]">
      <InlineMarkdown text={lines.join(' ')} />
    </p>
  );
}

function startsMarkdownBlock(cursor: MarkdownCursor) {
  const current = cursor.lines[cursor.index].trim();
  if (!current || current.startsWith('```') || current.startsWith('$$') || current.startsWith('>'))
    return true;
  if (/^[-\*\_]{3,}$/.test(current)) return true;
  if (/^(?:#{1,6}\s+|[-*]\s+|\d+\.\s+)/.test(current)) return true;
  return isTableStart(cursor, current);
}

function fallbackCopy(text: string) {
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.style.position = 'fixed';
  textarea.style.opacity = '0';
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand('copy');
  document.body.removeChild(textarea);
}

export function MarkdownOutput({ markdown }: Readonly<{ markdown: string }>) {
  const [view, setView] = useState<'preview' | 'source'>('preview');
  const [copied, setCopied] = useState(false);
  const copyTimeoutRef = useRef<number | undefined>(undefined);
  const lineCount = markdown ? markdown.replace(/\r\n/g, '\n').split('\n').length : 0;

  useEffect(() => {
    const copyTimeout = copyTimeoutRef;
    return () => {
      if (copyTimeout.current) window.clearTimeout(copyTimeout.current);
    };
  }, []);

  function copyMarkdown() {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(markdown).catch(() => {
        fallbackCopy(markdown);
      });
    } else {
      fallbackCopy(markdown);
    }
    setCopied(true);
    if (copyTimeoutRef.current) window.clearTimeout(copyTimeoutRef.current);
    copyTimeoutRef.current = window.setTimeout(() => setCopied(false), 1400);
  }

  return (
    <div className="min-h-[55vh]">
      <div className="border-border bg-panel sticky top-0 z-10 flex flex-wrap items-center justify-between gap-3 rounded-t-[var(--radius-md)] border border-b-0 px-3 py-2">
        <div className="flex items-center gap-2">
          <button
            type="button"
            aria-pressed={view === 'preview'}
            onClick={() => setView('preview')}
            className={`rounded-sm px-3 py-1.5 text-sm font-medium transition-colors ${
              view === 'preview'
                ? 'bg-accent text-accent-fg'
                : 'text-secondary hover:bg-background-alt hover:text-foreground'
            }`}
          >
            Preview
          </button>
          <button
            type="button"
            aria-pressed={view === 'source'}
            onClick={() => setView('source')}
            className={`rounded-sm px-3 py-1.5 text-sm font-medium transition-colors ${
              view === 'source'
                ? 'bg-accent text-accent-fg'
                : 'text-secondary hover:bg-background-alt hover:text-foreground'
            }`}
          >
            Source
          </button>
          <span className="text-secondary font-mono text-xs">{lineCount} lines</span>
        </div>
        <Button variant="quiet" type="button" onClick={copyMarkdown}>
          <Copy className="size-3.5" />
          {copied ? 'Copied' : 'Copy'}
        </Button>
      </div>
      <article className="surface-muted bg-background max-h-[62vh] min-h-[55vh] overflow-y-auto rounded-b-[var(--radius-md)] border">
        {view === 'preview' ? (
          <MarkdownPreview markdown={markdown} />
        ) : (
          <pre className="min-h-[55vh] overflow-auto p-4 text-xs leading-relaxed whitespace-pre-wrap">
            <code className="font-mono">{markdown}</code>
          </pre>
        )}
      </article>
    </div>
  );
}

export function MarkdownOutputPanel({
  isLoading,
  markdown,
  emptyTitle,
  emptyDescription,
}: Readonly<{
  isLoading: boolean;
  markdown: string;
  emptyTitle: string;
  emptyDescription: string;
}>) {
  if (isLoading) {
    return (
      <div className="min-h-[55vh]">
        <DataRegionLoading count={5} className="px-0" />
      </div>
    );
  }
  if (!markdown) {
    return (
      <div className="min-h-[55vh]">
        <DataRegionEmpty title={emptyTitle} description={emptyDescription} className="px-0" />
      </div>
    );
  }
  return <MarkdownOutput markdown={markdown} />;
}
