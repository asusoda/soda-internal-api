// Apps, their deployments and the pod of an app on its hosting provider.

export type AppManifest = Record<string, unknown>;

export type AppDeployment = {
  id: number;
  tag: string;
  status: 'deploying' | 'healthy' | 'failed';
  actor: string | null;
  error: string | null;
  manifest_ref: string | null;
  started_at: string | null;
  finished_at: string | null;
};

export type AppKind = 'bot' | 'agent' | 'site' | 'service';

export type App = {
  name: string;
  kind: AppKind;
  description: string | null;
  url: string | null;
  // host and provider both name the hosting provider; host is the older key
  host: string;
  provider: string;
  manifest: AppManifest;
  repo: string | null;
  manifest_path: string | null;
  pod_id: string | null;
  current_tag: string | null;
  latest_deployment: AppDeployment | null;
  updated_at: string | null;
};

export type AppDetail = App & { deployments: AppDeployment[] };

// The provider call a deploy makes, as a dry run returns it. Secret env values show as (secret).
export type DeployPreview = {
  dry_run: true;
  tag: string;
  manifest: AppManifest;
  request: { method: string; path: string; body: Record<string, unknown> };
};

// A pod as the RunPod REST API returns it. Only the fields the dashboard reads are named.
export type RunPodPod = {
  id?: string;
  name?: string;
  desiredStatus?: string;
  image?: string;
  costPerHr?: number | string;
  publicIp?: string | null;
  lastStartedAt?: string | null;
  gpu?: { displayName?: string; count?: number } | null;
  machine?: { gpuDisplayName?: string; cpuTypeId?: string; location?: string; dataCenterId?: string } | null;
  [field: string]: unknown;
};

// A container on This server, as the runner describes it.
export type ServerPod = {
  id: string;
  state: string;
  image: string | null;
  started_at: string | null;
  memory_mb: number;
  cpus: number;
  ports: { container: number; host: number }[];
};

// An app template from GET /api/dashboard/<org>/apps/templates. Secret inputs become org secrets.
export type AppTemplateInput = {
  key: string;
  kind: 'image' | 'env' | 'secret' | 'volume' | 'data_center';
  label: string;
  required: boolean;
};

export type AppTemplate = {
  name: string;
  title: string;
  summary: string;
  kind: AppKind;
  tag: string | null;
  inputs: AppTemplateInput[];
  manifest: AppManifest;
};

// The answer to POST /api/dashboard/<org>/apps/templates/<template>.
export type AppFromTemplate = App & { template: string; suggested_tag: string | null };

// A shared app as an org sees it: the deployment owns it, and the org subscribes to use it.
export type SharedApp = {
  name: string;
  kind: AppKind;
  description: string | null;
  url: string | null;
  // What a subscription does: vaultwarden invites each email to the vault
  access: 'vaultwarden' | null;
  current_tag: string | null;
  subscribers: number;
  subscribed: boolean;
  invited: string[];
};

export type SharedAppSubscribe = { name: string; subscribed: boolean; results: Record<string, string>; invited: string[] };

// A shared app on the Superadmin page: an app with no org, and how many orgs subscribe.
export type SharedAppAdmin = App & { subscribers: number };
