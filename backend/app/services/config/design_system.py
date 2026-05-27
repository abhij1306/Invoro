from __future__ import annotations

DESIGN_SYSTEM_SURFACE = "design_system"
DESIGN_SYSTEM_MARKDOWN_TASK = "design_system_markdown"
DESIGN_SYSTEM_EXPORT_FILENAME = "design.md"

DESIGN_SYSTEM_DEFAULT_SAMPLE_URLS = 6
DESIGN_SYSTEM_SITEMAP_SCAN_MULTIPLIER = 3

DESIGN_SYSTEM_PUBLIC_FIELDS = (
    "title",
    "design_tokens",
    "source_urls",
    "generation_metadata",
    "url",
)

DESIGN_SYSTEM_RECORD_TYPE = "design_system"
DESIGN_SYSTEM_SOURCE = "design_system_extractor"

DESIGN_SYSTEM_INTERNAL_VARIABLE_PREFIXES = (
    "--tw-",
    "--swiper-",
    "--radix-",
    "--squeak-",
    "--toastify-",
    "--animate-",
)

DESIGN_SYSTEM_COLOR_ROLE_HINTS = {
    "primary": ("text-primary", "primary", "brand-primary"),
    "secondary": ("text-secondary", "secondary", "brand-secondary"),
    "tertiary": ("accent", "tertiary", "brand-accent", "cta"),
    "neutral": ("bg", "background", "neutral", "canvas"),
    "surface": ("surface", "card", "panel"),
    "border": ("border", "stroke", "outline"),
    "muted": ("muted", "subtle"),
}

DESIGN_SYSTEM_SPACING_TOKEN_NAMES = ("xs", "sm", "md", "lg", "xl", "2xl", "3xl")
DESIGN_SYSTEM_ROUNDED_TOKEN_NAMES = ("sm", "md", "lg", "xl", "full")

DESIGN_SYSTEM_BROWSER_SNAPSHOT_SCRIPT = r"""
() => {
  const maxValues = 2400;
  const maxComponents = 80;
  const cssVariables = {};
  for (const sheet of Array.from(document.styleSheets || [])) {
    let rules = [];
    try {
      rules = Array.from(sheet.cssRules || []);
    } catch {
      continue;
    }
    for (const rule of rules) {
      const style = rule && rule.style;
      if (!style) continue;
      for (const name of Array.from(style)) {
        if (name && name.startsWith('--')) {
          const value = String(style.getPropertyValue(name) || '').trim();
          if (value) cssVariables[name] = value;
        }
      }
    }
  }

  const values = {
    colors: [],
    fonts: [],
    fontSizes: [],
    fontWeights: [],
    lineHeights: [],
    spacing: [],
    radius: [],
    shadows: [],
  };
  const components = [];
  const seenComponents = new Set();
  const push = (key, value) => {
    const text = String(value || '').trim();
    if (!text || text === 'normal' || text === 'none' || text === '0px') return;
    const list = values[key];
    if (list.length < maxValues) list.push(text);
  };
  const visible = (node, style) => {
    const rect = node.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
  };
  const classify = (node) => {
    const tag = String(node.tagName || '').toLowerCase();
    const role = String(node.getAttribute('role') || '').toLowerCase();
    if (tag === 'button' || role === 'button' || (tag === 'a' && /button|btn|cta/i.test(node.className || ''))) return 'button';
    if (tag === 'input' || tag === 'select' || tag === 'textarea') return 'input';
    if (tag === 'nav' || role === 'navigation') return 'nav';
    if (tag === 'table' || role === 'table') return 'table';
    if (tag === 'header') return 'header';
    if (tag === 'footer') return 'footer';
    if (/card|tile|panel|product|article/i.test(node.className || '')) return 'card';
    return '';
  };
  for (const node of Array.from(document.querySelectorAll('body, h1, h2, h3, p, a, button, input, select, textarea, nav, header, footer, main, section, article, table, [role], [class]')).slice(0, 1200)) {
    const style = window.getComputedStyle(node);
    if (!visible(node, style)) continue;
    push('colors', style.color);
    push('colors', style.backgroundColor);
    push('fonts', style.fontFamily);
    push('fontSizes', style.fontSize);
    push('fontWeights', style.fontWeight);
    push('lineHeights', style.lineHeight);
    push('spacing', style.marginTop);
    push('spacing', style.marginRight);
    push('spacing', style.marginBottom);
    push('spacing', style.marginLeft);
    push('spacing', style.paddingTop);
    push('spacing', style.paddingRight);
    push('spacing', style.paddingBottom);
    push('spacing', style.paddingLeft);
    push('radius', style.borderRadius);
    push('shadows', style.boxShadow);
    const kind = classify(node);
    if (kind) {
      const signature = `${kind}|${style.fontSize}|${style.fontWeight}|${style.color}|${style.backgroundColor}|${style.borderRadius}|${style.paddingTop} ${style.paddingRight}`;
      if (!seenComponents.has(signature) && components.length < maxComponents) {
        seenComponents.add(signature);
        components.push({
          kind,
          tag: String(node.tagName || '').toLowerCase(),
          text: String(node.innerText || node.getAttribute('aria-label') || '').trim().slice(0, 80),
          font_size: style.fontSize,
          font_weight: style.fontWeight,
          color: style.color,
          background: style.backgroundColor,
          radius: style.borderRadius,
          padding: `${style.paddingTop} ${style.paddingRight} ${style.paddingBottom} ${style.paddingLeft}`,
          shadow: style.boxShadow,
        });
      }
    }
  }
  return {
    url: location.href,
    title: document.title || '',
    css_variables: cssVariables,
    values,
    components,
  };
}
"""

DESIGN_SYSTEM_LLM_SYSTEM_PROMPT = "Return JSON only. Shape prose from supplied deterministic design tokens. Do not invent, remove, rename, or change token values."
