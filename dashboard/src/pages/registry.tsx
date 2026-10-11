import {
  Activity,
  BriefcaseBusiness,
  CalendarDays,
  CodeXml,
  Coins,
  Compass,
  Database,
  HeartPulse,
  KeyRound,
  LayoutDashboard,
  Cpu,
  Server,
  Settings,
  ShieldCheck,
  ShoppingBag,
  Trophy,
  Megaphone,
} from 'lucide-react';
import type { QueryClient } from '@tanstack/react-query';
import type { ComponentType, ReactNode } from 'react';
import { ModuleGate } from '../components/module-gate';
import { overviewQuery } from '../lib/queries';
import { ActivityPage } from './activity';
import { AdminPage } from './admin';
import { HackathonWebhookPage, JobWebhookPage } from './feeds';
import { CalendarPage } from './calendar';
import { ExplorePage } from './explore';
import { GodfatherPage } from './godfather';
import { HostingPage } from './hosting';
import { KnowledgePage } from './knowledge';
import { KnowledgeSourcePage } from './knowledge/source';
import { LeetCodePage } from './leetcode';
import { OverviewPage } from './overview';
import { PointsPage } from './points';
import { prefetchPoints } from './points/shared';
import { SettingsPage } from './settings';
import { StorePage } from './store';
import { prefetchStore } from './store/shared';
import { TokensPage } from './tokens';
import { UptimePage } from './uptime';
import { AlertsPage } from './alerts';

// The sidebar sections, in order. A section with no title has no header. They follow the categories on Explore.
export const SECTIONS = [
  { id: 'top' },
  { id: 'storage', title: 'Storage' },
  { id: 'agents', title: 'AI and agents' },
  { id: 'automations', title: 'Automations' },
  { id: 'bots', title: 'Bots' },
  { id: 'compute', title: 'Compute' },
  { id: 'bottom' },
] as const;

export type SectionId = (typeof SECTIONS)[number]['id'];

export type PageEntry = {
  // The URL after /<org>/. An empty path is the org home page.
  path: string;
  // The sidebar label, and the page title on the module-off note.
  label: string;
  icon: ComponentType<{ className?: string }>;
  section: SectionId;
  // The sidebar hides the page when the API says this module is off. With a list, it hides the page when every
  // module in the list is off.
  module?: string | string[];
  // With one module set, the page shows a module-off note in place of its content when the module is off.
  gate?: boolean;
  // Only the superadmin sees the page in the sidebar.
  superadmin?: boolean;
  // The page has no sidebar item. Links on another page open it. The first part of path selects the sidebar item.
  hidden?: boolean;
  page: ComponentType;
  // Starts the main requests of the page: on a sidebar hover or focus, and when the page opens, before its module
  // check answers.
  prefetch?: (client: QueryClient, prefix: string) => void;
};

const prefetchOverview = (client: QueryClient, prefix: string) => void client.prefetchQuery(overviewQuery(prefix));

// Every org page, in sidebar order. To add a page, write the page file and add one entry here.
export const PAGES: PageEntry[] = [
  { path: '', label: 'Overview', icon: LayoutDashboard, section: 'top', page: OverviewPage, prefetch: prefetchOverview },
  { path: 'explore', label: 'Explore', icon: Compass, section: 'top', page: ExplorePage },
  { path: 'knowledge', label: 'Knowledge', icon: Database, section: 'storage', module: 'knowledge', gate: true, page: KnowledgePage },
  { path: 'knowledge/sources/*', label: 'Knowledge source', icon: Database, section: 'storage', module: 'knowledge', gate: true, hidden: true, page: KnowledgeSourcePage },
  { path: 'points', label: 'Points', icon: Coins, section: 'storage', module: 'points', gate: true, page: PointsPage, prefetch: prefetchPoints },
  { path: 'store', label: 'Store', icon: ShoppingBag, section: 'storage', module: 'storefront', gate: true, page: StorePage, prefetch: prefetchStore },
  { path: 'job-alerts', label: 'Job alerts', icon: BriefcaseBusiness, section: 'automations', module: 'feeds', gate: true, page: JobWebhookPage },
  { path: 'hackathons', label: 'Hackathons', icon: Trophy, section: 'automations', module: 'feeds', gate: true, page: HackathonWebhookPage },
  { path: 'calendar', label: 'Calendar', icon: CalendarDays, section: 'automations', module: 'calendar', gate: true, page: CalendarPage },
  { path: 'uptime', label: 'Uptime', icon: HeartPulse, section: 'automations', module: 'uptime', gate: true, page: UptimePage },
  { path: 'leetcode', label: 'LeetCode', icon: CodeXml, section: 'bots', module: 'leetcode', gate: true, page: LeetCodePage },
  { path: 'godfather', label: 'Godfather', icon: Cpu, section: 'compute', module: 'godfather', gate: true, page: GodfatherPage },
  { path: 'hosting', label: 'Hosting', icon: Server, section: 'compute', module: 'runpod', gate: true, page: HostingPage },
  { path: 'alerts', label: 'Alerts', icon: Megaphone, section: 'bottom', page: AlertsPage },
  { path: 'tokens', label: 'Tokens', icon: KeyRound, section: 'bottom', page: TokensPage },
  { path: 'activity', label: 'Activity', icon: Activity, section: 'bottom', page: ActivityPage },
  { path: 'settings', label: 'Settings', icon: Settings, section: 'bottom', page: SettingsPage },
  { path: 'admin', label: 'Superadmin', icon: ShieldCheck, section: 'bottom', superadmin: true, page: AdminPage },
];

// Old org paths that open another page. to is relative to the old path.
export const REDIRECTS: { path: string; to: string }[] = [
  { path: 'ci', to: '../activity?tab=ci' },
  { path: 'notifications', to: '../activity' },
  { path: 'modules', to: '../explore' },
  { path: 'integrations', to: '../explore?tab=integrations' },
  { path: 'apps', to: '../hosting' },
  { path: 'compute', to: '../godfather' },
  { path: 'mcp', to: '../tokens' },
  { path: 'webhooks', to: '../alerts' },
  { path: 'agents', to: '../explore' },
];

// The element for the route of a page, inside a ModuleGate when the entry asks for one.
export function pageElement({ page: Page, module, gate, label }: PageEntry): ReactNode {
  return typeof module === 'string' && gate ? (
    <ModuleGate module={module} title={label}>
      <Page />
    </ModuleGate>
  ) : (
    <Page />
  );
}
