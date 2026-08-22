import nextVitals from 'eslint-config-next/core-web-vitals';
import eslintConfigPrettier from 'eslint-config-prettier';

const config = [
  ...nextVitals,
  {
    ignores: ['.next/**', 'next-env.d.ts', 'node_modules/**'],
  },
  {
    files: ['**/*.{js,jsx,mjs,cjs,ts,tsx}'],
    rules: {
      complexity: ['error', 15],
    },
  },
  eslintConfigPrettier,
];

export default config;
