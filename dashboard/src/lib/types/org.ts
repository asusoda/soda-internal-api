// Orgs, their settings, secrets, tokens and the audit log.

export type Organization = { id: number; name: string; prefix: string; guild_id: string; icon_url: string | null };

export type OrganizationDetail = Organization & {
  description: string | null;
  is_active: boolean;
  officer_role_id: string | null;
  points_per_message: number | null;
  points_cooldown: number | null;
  created_at: string | null;
  updated_at: string | null;
};

export type Branding = { logo_url: string | null; accent_color: string | null; website_url: string | null };

export type ModuleState = { name: string; description: string; enabled: boolean };

// An integration or a setting that a module needs. connected says whether the org or the deployment set it.
export type ModuleNeed = {
  key: string;
  label: string;
  kind: 'integration' | 'setting';
  optional: boolean;
  connected: boolean;
};

export type ModuleSubmodule = { name: string; title: string; description: string };

// A module on Explore. ready is false while a need that is not optional is not connected.
export type CatalogModule = {
  name: string;
  title: string;
  description: string;
  category: string;
  switchable: boolean;
  enabled: boolean;
  ready: boolean;
  needs: ModuleNeed[];
  submodules: ModuleSubmodule[];
  // The limits this module's use counts against
  limits: { key: string; label: string; window: string | null; paid_by: 'org' | 'metered' }[];
};

export type ModuleCatalog = { categories: string[]; modules: CatalogModule[] };

export type SecretState = { name: string; description: string; set: boolean };

// A connected service whose tools a token can get, with its scopes and the limits it takes.
export type TokenIntegration = {
  key: string;
  title: string;
  connected: boolean;
  // Scopes that give the integration's own tools
  scopes: string[];
  // Platform scopes that call the integration for the agent
  through?: string[];
  limits: string[];
  // The Platform tools each of its scopes gives, by scope
  tools?: Record<string, string[]>;
  // The tools come from the service's own MCP server
  remote?: boolean;
  // The modules that use the integration
  used_by?: string[];
};

export type MachineToken = {
  id: number;
  name: string;
  kind: string;
  scopes: string[];
  // Per-integration limits, such as { github: { repos: ['my-org/*'] } }
  limits: Record<string, Record<string, string[]>>;
  display: string;
  created_by: string | null;
  created_at: string | null;
  expires_at: string | null;
  last_used_at: string | null;
};

export type AuditEntry = {
  id: number;
  created_at: string | null;
  source: string;
  action: string;
  org: string | null;
  actor_kind: string | null;
  actor_id: string | null;
  status: number | null;
  details: Record<string, unknown> | null;
};

// A submodule: a domain such as a campus or careers that an org subscribes to (GET /api/dashboard/<org>/submodules).
export type Submodule = {
  name: string;
  title: string;
  description: string;
  key_prefix: string;
  pages: number;
  queries: string[];
  feeds: string[];
  // Shared pages and their last crawl, for every subscriber
  sources: number;
  last_crawl: string | null;
  subscribed: boolean;
  subscribers: number;
  // The modules that read the submodule
  modules: string[];
  // What the submodule brings and who pays for each part
  parts: { kind: 'pages' | 'queries' | 'feeds'; count: number; paid_by: 'org' | 'shared'; module: string }[];
};
