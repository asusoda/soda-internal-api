// One key of an integration. A secret value is never sent back; set says whether the org saved one.
// value is the saved value of a field that is not secret, such as a URL.
export type IntegrationField = {
  name: string;
  label: string;
  hint: string;
  kind: 'text' | 'url' | 'json';
  secret: boolean;
  optional: boolean;
  set: boolean;
  value: string | null;
  updated_at: string | null;
};

// An outside service. source is org (the org's keys), deployment (the default in Doppler) or null (not connected).
export type Integration = {
  key: string;
  title: string;
  description: string;
  docs: string | null;
  fields: IntegrationField[];
  editable: boolean;
  source: 'org' | 'deployment' | null;
  // With the deployment's keys, the org's use counts against these limits
  metered_by: { key: string; label: string }[];
  testable: boolean;
  used_by: string[];
  // The titles of the modules on Explore that need the integration
  unlocks?: string[];
};

// An OAuth sign-in that gives agents the tools of the service's own MCP server.
export type OAuthState = {
  title: string;
  connected: boolean;
  connected_by: string | null;
  connected_at: string | null;
  // Why the sign-in cannot start on this server, or null
  blocked: string | null;
};

export type IntegrationList = {
  integrations: Integration[];
  oauth?: Record<string, OAuthState>;
  secrets_key: boolean;
};

export type IntegrationTest = { ok: boolean; message: string };

// One ASU sign-in attempt. state: running, duo_code (code is the number to enter in Duo), done or failed (reason says why).
export type AsuAttempt = {
  state: 'running' | 'duo_code' | 'done' | 'failed';
  message: string;
  code: string | null;
  reason: string | null;
  started_at: string;
  finished_at: string | null;
};

// The org's ASU sign-in. The API keeps only the browser cookies, never the NetID or the password.
export type AsuState = {
  title: string;
  signed_in: boolean;
  signed_in_by: string | null;
  signed_in_at: string | null;
  // When a tool found the session expired, or null
  expired_at: string | null;
  // Why the sign-in cannot start on this server, or null
  blocked: string | null;
  attempt: AsuAttempt | null;
};
