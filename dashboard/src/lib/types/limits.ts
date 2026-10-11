// Per-org limits (core/limits.py) and the server's health (core/host.py).

// minute, hour or day for a rate limit; null for a count limit.
export type LimitWindow = 'minute' | 'hour' | 'day' | null;

export type LimitEntry = {
  key: string;
  module: string;
  label: string;
  unit: string;
  window: LimitWindow;
  // The value from .env or the declared default. null means no limit.
  default: number | null;
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
