// Extra padding (in ch) added so wrapped JSON lines align cleanly past the key.
const WRAP_ALIGN_EXTRA = 4;

function escapeHtml(input: string): string {
  return input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function displayJsonStringToken(token: string): string {
  const hasColon = token.endsWith(':');
  const rawString = hasColon ? token.slice(0, -1) : token;
  try {
    return `"${JSON.parse(rawString)}"${hasColon ? ':' : ''}`;
  } catch {
    return token;
  }
}

export function syntaxHighlightJson(json: string) {
  if (!json) return '';

  // Walk the input with a tokenizer regex; escape both matched tokens and the
  // gaps between them so any unmatched character is rendered as text, not HTML.
  const tokenRegex =
    /("(\\u[a-fA-F0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?|[\{\}\[\],])/g;
  let highlighted = '';
  let lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = tokenRegex.exec(json)) !== null) {
    if (m.index > lastIndex) {
      highlighted += escapeHtml(json.slice(lastIndex, m.index));
    }
    const match = m[0];
    if (/^[\{\}\[\],]$/.test(match)) {
      highlighted += `<span class="syntax-punct">${escapeHtml(match)}</span>`;
    } else {
      let cls = 'syntax-number';
      let displayToken = match;
      if (match.startsWith('"')) {
        cls = /:$/.test(match) ? 'syntax-key' : 'syntax-string';
        displayToken = displayJsonStringToken(match);
      } else if (match === 'true' || match === 'false') {
        cls = 'syntax-boolean';
      } else if (match === 'null') {
        cls = 'syntax-null';
      }
      highlighted += `<span class="${cls}">${escapeHtml(displayToken)}</span>`;
    }
    lastIndex = m.index + match.length;
  }
  if (lastIndex < json.length) {
    highlighted += escapeHtml(json.slice(lastIndex));
  }

  return highlighted
    .split('\n')
    .map((line) => {
      const spaces = line.match(/^(\s*)/)![1].length;
      const indent = spaces + WRAP_ALIGN_EXTRA;
      return `<span style="display: block; padding-left: ${indent}ch; text-indent: -${indent}ch;">${line}</span>`;
    })
    .join('');
}
