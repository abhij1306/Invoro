import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const failures = [];

const lineBudgets = new Map([
  ['components/ui/primitives.tsx', 30],
  ['components/ui/patterns.tsx', 40],
  ['components/crawl/shared.ts', 200],
  ['components/crawl/shared-components.tsx', 120],
  ['components/layout/app-shell.tsx', 460],
  ['components/layout/sidebar.tsx', 210],
]);

function read(relativePath) {
  try {
    return fs.readFileSync(path.join(root, relativePath), 'utf8');
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    failures.push(`${relativePath} could not be read: ${message}`);
    return null;
  }
}

for (const [relativePath, maxLines] of lineBudgets) {
  const content = read(relativePath);
  if (content === null) continue;
  const lines = content === '' ? 0 : content.replace(/\r?\n$/, '').split(/\r?\n/).length;
  if (lines > maxLines) {
    failures.push(`${relativePath} has ${lines} lines; limit is ${maxLines}.`);
  }
}

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

for (const relativePath of requiredOwners) {
  if (!fs.existsSync(path.join(root, relativePath))) {
    failures.push(`${relativePath} is missing. Keep shared concerns in focused owners.`);
  }
}

function sourceFiles(directory) {
  if (!fs.existsSync(directory)) return [];
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const absolutePath = path.join(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(absolutePath);
    if (
      !entry.isFile() ||
      !/\.(?:ts|tsx)$/.test(entry.name) ||
      /\.(?:test|spec)\./.test(entry.name)
    ) {
      return [];
    }
    return [absolutePath];
  });
}

for (const directory of ['app', 'components']) {
  for (const absolutePath of sourceFiles(path.join(root, directory))) {
    const relativePath = path.relative(root, absolutePath).replaceAll('\\', '/');
    const content = fs.readFileSync(absolutePath, 'utf8');
    if (/\btransition-all\b/.test(content)) {
      failures.push(`${relativePath} uses transition-all; name the animated properties.`);
    }
  }
}

const fontFiles = [
  'app/fonts/Satoshi-Variable.woff2',
  'app/fonts/Satoshi-VariableItalic.woff2',
  'app/fonts/Switzer-Variable.woff2',
  'app/fonts/Switzer-VariableItalic.woff2',
];
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
