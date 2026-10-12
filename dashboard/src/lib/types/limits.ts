// Per-org limits (core/limits.py) and the server's health (core/host.py).

// minute, hour or day for a rate limit; null for a count limit.
export type LimitWindow = 'minute' | 'hour' | 'day' | null;

// Who pays for what a limit counts: the org's own data and apps, or a shared service the org uses.
// shared is content the deployment makes once for every org, such as a submodule's pages; it has no limit of an org.
export type PaidBy = 'org' | 'shared' | 'metered';

export type LimitEntry = {
  key: string;
  module: string;
  label: string;
  unit: string;
  window: LimitWindow;
  // The value from Doppler or the declared default. null means no limit.
  default: number | null;
  paid_by: 'org' | 'metered';
  integrations: string[];
};

export type LimitRow = LimitEntry & {
  // The value for the org. null means no limit.
  value: number | null;
  override: boolean;
  used: number;
  // Whether the limit's module is on for the org.
  enabled: boolean;
};

export type LimitOverride = { key: string; value: number | null; updated_at: string | null; updated_by: string | null };

export type OrgLimits = {
  org: { id: number; name: string; prefix: string; is_active: boolean };
  limits: LimitRow[];
  near: string[];
  overrides: LimitOverride[];
};

export type AllLimits = { catalog: LimitEntry[]; near: number; orgs: OrgLimits[] };

// A new value for one limit: a number, null for no limit, or "default" to remove the override.
export type LimitChange = number | null | 'default';

export type ServerHealth = {
  cpus: number | null;
  load: number[] | null;
  uptime_seconds: number | null;
  memory: { total: number; available: number } | null;
  disk: { total: number; used: number; free: number } | null;
  database_bytes: number | null;
  database: string;
  container: {
    memory_used: number | null;
    memory_limit: number | null;
    cpu_limit: number | null;
    process_uptime_seconds: number;
  };
  bot_ready: boolean | null;
  jobs: { backend: string; queue: Record<string, number> | null };
};

// A container or host process that the host agent lists (deploy/host-agent), with its owner.
export type ServerService = {
  name: string;
  kind: 'container' | 'process';
  state: string | null;
  status: string | null;
  image: string | null;
  project: string | null;
  memory_used: number | null;
  memory_limit: number | null;
  cpu_percent: number | null;
  ports: number[];
  domains: string[];
  owner: 'platform' | 'infrastructure' | 'org' | null;
  org: { id: number; name: string; prefix: string } | null;
  // Whether the superadmin set the owner; else it comes from the container's labels
  set: boolean;
};

export type ServerServices = {
  agent: { age_seconds: number; stale: boolean } | null;
  services: ServerService[];
};
