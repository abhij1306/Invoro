import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = process.cwd();
const failures = [];
const isMain = path.resolve(process.argv[1] ?? '') === fileURLToPath(import.meta.url);
export const MAX_PHYSICAL_LINES = 800;
export const SOURCE_SCAN_EXCLUDED_DIRECTORIES = new Set([
  '.git',
  '.cache',
  '.next',
  '.turbo',
  'build',
  'coverage',
  'dist',
  'htmlcov',
  'node_modules',
  'playwright-report',
  'test-results',
]);

const requiredOwners = [
  'components/ui/dropdown.tsx',
  'components/ui/field.tsx',
  'components/ui/skeleton.tsx',
  'components/ui/toggle.tsx',
  'components/ui/tooltip.tsx',
  'components/ui/typography.tsx',
  'components/ui/patterns/controls.tsx',
  'components/ui/patterns/data-display.tsx',
  'components/ui/patterns/page-header.tsx',
  'components/ui/patterns/run-workspace.tsx',
  'components/ui/patterns/sections.tsx',
  'components/crawl/shared.ts',
  'components/crawl/shared-components.tsx',
];

if (isMain) {
  for (const relativePath of requiredOwners) {
    if (!fs.existsSync(path.join(root, relativePath))) {
      failures.push(`${relativePath} is missing. Keep shared concerns in focused owners.`);
    }
  }
}

export function physicalLineCount(content) {
  return content === '' ? 0 : content.replace(/\r?\n$/, '').split(/\r?\n/).length;
}

export function sourceFiles(directory, includeTests = true) {
  if (!fs.existsSync(directory)) return [];
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const absolutePath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      return SOURCE_SCAN_EXCLUDED_DIRECTORIES.has(entry.name)
        ? []
        : sourceFiles(absolutePath, includeTests);
    }
    if (
      !entry.isFile() ||
      !/\.(?:[cm]?js|jsx|ts|tsx)$/.test(entry.name) ||
      entry.name === 'next-env.d.ts' ||
      /\.min\.(?:js|jsx)$/.test(entry.name) ||
      (!includeTests && /\.(?:test|spec)\./.test(entry.name))
    ) {
      return [];
    }
    return [absolutePath];
  });
}

if (isMain) {
  for (const absolutePath of sourceFiles(root)) {
    const relativePath = path.relative(root, absolutePath).replaceAll('\\', '/');
    const lines = physicalLineCount(fs.readFileSync(absolutePath, 'utf8'));
    if (lines > MAX_PHYSICAL_LINES) {
      failures.push(`${relativePath} has ${lines} physical lines; limit is ${MAX_PHYSICAL_LINES}.`);
    }
  }
}

if (isMain) {
  for (const directory of ['app', 'components']) {
    for (const absolutePath of sourceFiles(path.join(root, directory), false)) {
      const relativePath = path.relative(root, absolutePath).replaceAll('\\', '/');
      const content = fs.readFileSync(absolutePath, 'utf8');
      if (/\btransition-all\b/.test(content)) {
        failures.push(`${relativePath} uses transition-all; name the animated properties.`);
      }
    }
  }
}

const fontFiles = [
  'app/fonts/Satoshi-Variable.woff2',
  'app/fonts/Satoshi-VariableItalic.woff2',
  'app/fonts/Switzer-Variable.woff2',
  'app/fonts/Switzer-VariableItalic.woff2',
];
if (isMain) {
  for (const relativePath of fontFiles) {
    if (!fs.existsSync(path.join(root, relativePath))) {
      failures.push(`${relativePath} is missing from the local typography contract.`);
    }
  }

  if (failures.length) {
    console.error('Frontend architecture check failed:');
    for (const failure of failures) console.error(`- ${failure}`);
    process.exit(1);
  }

  console.log('Frontend architecture check passed.');
}
