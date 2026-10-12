import react from '@vitejs/plugin-react';
import autoprefixer from 'autoprefixer';
import tailwindcss from 'tailwindcss';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  // Docker, CI and .env set REACT_APP_API_URL, the name from Create React App.
  envPrefix: 'REACT_APP_',
  css: { postcss: { plugins: [tailwindcss(), autoprefixer()] } },
  // Dockerfile.web serves build/.
  build: { outDir: 'build' },
  server: { port: 5000 },
  preview: { port: 5000 },
  test: { environment: 'jsdom', setupFiles: ['./src/setupTests.ts'] },
});
