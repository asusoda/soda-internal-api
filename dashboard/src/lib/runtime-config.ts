// The settings that the dashboard container writes to /config.js when it starts (deploy/frontend-config.mjs).
// public/config.js is empty, so `npm run dev` and a static deploy use the values that Vite built in.
declare global {
  interface Window {
    __PLATFORM_CONFIG__?: Record<string, string | undefined>;
  }
}

export function runtimeSetting(name: string): string | undefined {
  if (typeof window === 'undefined') return undefined;
  return window.__PLATFORM_CONFIG__?.[name] || undefined;
}
