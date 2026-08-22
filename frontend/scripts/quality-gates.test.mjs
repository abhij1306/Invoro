import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

import { SOURCE_SCAN_EXCLUDED_DIRECTORIES, sourceFiles } from './check-frontend-architecture.mjs';

const root = process.cwd();
const architectureScript = path.join(root, 'scripts', 'check-frontend-architecture.mjs');
const fixture = path.join(root, 'scripts', '__quality_gate_boundary__.ts');
const excludedFixtureDirectory = path.join(root, 'dist', '__quality_gate_boundary__');

function runArchitectureCheck() {
  return execFileSync(process.execPath, [architectureScript], {
    cwd: root,
    encoding: 'utf8',
    stdio: 'pipe',
  });
}

test('physical LOC gate passes at 800, fails at 801, and skips explicit artifacts', () => {
  try {
    fs.mkdirSync(excludedFixtureDirectory, { recursive: true });
    fs.writeFileSync(
      path.join(excludedFixtureDirectory, 'ignored.ts'),
      '// ignored\n'.repeat(801),
      'utf8',
    );
    fs.writeFileSync(fixture, '// exact\n'.repeat(800), 'utf8');
    assert.doesNotThrow(runArchitectureCheck);

    fs.writeFileSync(fixture, '// oversized\n'.repeat(801), 'utf8');
    assert.throws(runArchitectureCheck, (error) =>
      String(error.stderr).includes(
        'scripts/__quality_gate_boundary__.ts has 801 physical lines; limit is 800.',
      ),
    );
  } finally {
    fs.rmSync(fixture, { force: true });
    fs.rmSync(excludedFixtureDirectory, { force: true, recursive: true });
  }
});

test('ESLint complexity gate passes at 15 and fails at 16', () => {
  const eslint = path.join(root, 'node_modules', 'eslint', 'bin', 'eslint.js');
  const source = (complexity) =>
    `function synthetic(value) {\n${Array.from(
      { length: complexity - 1 },
      (_, index) => `  if (value === ${index}) return ${index};\n`,
    ).join('')}  return -1;\n}\n`;

  try {
    fs.writeFileSync(fixture, source(15), 'utf8');
    assert.doesNotThrow(() =>
      execFileSync(process.execPath, [eslint, fixture, '--max-warnings=0'], {
        cwd: root,
        stdio: 'pipe',
      }),
    );

    fs.writeFileSync(fixture, source(16), 'utf8');
    assert.throws(
      () =>
        execFileSync(process.execPath, [eslint, fixture, '--max-warnings=0'], {
          cwd: root,
          stdio: 'pipe',
        }),
      (error) => String(error.stdout).includes('complexity of 16. Maximum allowed is 15'),
    );
  } finally {
    fs.rmSync(fixture, { force: true });
  }
});

test('source scan exclusions skip only explicit artifact directories', () => {
  const workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'invoro-quality-gate-'));
  const maintained = path.join(workspace, 'app', 'maintained.ts');
  try {
    fs.mkdirSync(path.dirname(maintained), { recursive: true });
    fs.writeFileSync(maintained, 'export {};\n', 'utf8');
    for (const directory of SOURCE_SCAN_EXCLUDED_DIRECTORIES) {
      const excluded = path.join(workspace, directory, 'ignored.ts');
      fs.mkdirSync(path.dirname(excluded), { recursive: true });
      fs.writeFileSync(excluded, '// ignored\n'.repeat(801), 'utf8');
    }
    assert.deepEqual(sourceFiles(workspace), [maintained]);
  } finally {
    fs.rmSync(workspace, { force: true, recursive: true });
  }
});
