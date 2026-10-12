// Links to the Platform repo, its docs and its landing page.

import { runtimeSetting } from './runtime-config';

// The original repo of Platform, by SoDA. LICENSE clause 4b requires a link to it.
export const SOURCE_URL = 'https://github.com/asusoda/platform';

// The repo that holds the docs and submodules.
export const REPO_URL = SOURCE_URL;

// The docs and landing site of Platform. VITE_SITE_URL points the links at another deployment of site/.
const SITE_URL =
  (runtimeSetting('VITE_SITE_URL') ?? (import.meta.env.VITE_SITE_URL as string | undefined))?.replace(/\/$/, '') ||
  'https://platform.ais-asu.com';

export const DOCS_URL = `${SITE_URL}/docs`;
export const ABOUT_URL = SITE_URL;

// background is the fill of the mark. The logos have fixed colors, so it does not follow the theme.
export type BuiltBy = { name: string; short: string; url: string; logo: string; background: string };

// The orgs that build Platform, in the order of the marks. To add an org, add one line and put its logo in public/orgs/.
export const BUILT_BY: BuiltBy[] = [
  {
    name: 'The AI Society at ASU',
    short: 'AI Society',
    url: 'https://ais-asu.com',
    logo: 'orgs/ais.svg',
    background: '#0a0a0a',
  },
  {
    name: 'Software Developers Association at ASU',
    short: 'SoDA',
    url: 'https://thesoda.io',
    logo: 'orgs/soda.svg',
    background: '#ffffff',
  },
];

// The names with commas between them and "and" before the last one.
export function joinNames(names: string[]): string {
  return names.length < 2 ? (names[0] ?? '') : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

// The label of the marks. The short form leaves out the school.
export const builtByLabel = (orgs: BuiltBy[] = BUILT_BY, short = false) =>
  `Built by ${joinNames(orgs.map((o) => o.short))}${short ? '' : ' at ASU'}`;

// A page of the docs site, such as modules/calendar or codebase/webhooks.
export const docsPage = (path: string) => `${SITE_URL}/docs/${path}`;
