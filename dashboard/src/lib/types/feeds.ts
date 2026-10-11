// The feeds of the Feeds module and their history.

// A feed that a submodule offers, with the kind and config to create it.
export type FeedPreset = {
  // The webhook module that runs the feed
  module: string;
  submodule: string;
  submodule_title: string;
  key: string;
  title: string;
  description: string;
  kind: 'github_jobs' | 'hackathons';
  config: Record<string, unknown>;
  every_hours: number;
  added: boolean;
};

export type Feed = {
  key: string;
  kind: 'github_jobs' | 'hackathons';
  config: Record<string, unknown>;
  every_hours: number;
  enabled: boolean;
  // The alert destination it posts to. Null for an older feed with its own webhook secret
  destination_id: number | null;
  webhook_set: boolean;
  seeded_at: string | null;
  last_run_at: string | null;
  last_error: string | null;
  posted: number;
};

export type FeedRun = {
  started_at: string;
  duration_ms: number;
  found: number | null;
  new: number | null;
  posted: number;
  recorded: boolean;
  error: string | null;
};

export type FeedRuns = {
  runs: FeedRun[];
  items: { title: string; posted: boolean; created_at: string }[];
};
