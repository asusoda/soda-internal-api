// API responses for a fictional org, used by screenshots.mjs. Every name, id and token here is made up.

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

export const ORG = { id: 1, name: 'Robotics Club', prefix: 'robotics', guild_id: '1290000000000000000', icon_url: null };

export const BRANDING = { logo_url: null, accent_color: '#2563eb', website_url: 'https://robotics.example.org' };

export const MODULES = [
  { name: 'points', description: 'Points, leaderboards and event check-ins', enabled: true },
  { name: 'storefront', description: 'Merch store paid with points', enabled: true },
  { name: 'calendar', description: 'Notion to Google Calendar sync and the public events feed', enabled: true },
  { name: 'games', description: "Jeopardy games in the org's Discord server", enabled: true },
  { name: 'leetcode', description: "Daily LeetCode post in the org's channel, with solve checks", enabled: true },
  { name: 'godfather', description: "GPU and CPU pods on the org's RunPod account that members SSH into", enabled: true },
  { name: 'feeds', description: 'New job listings and hackathons posted to Discord webhooks', enabled: true },
  { name: 'uptime', description: 'Checks of sites and Hosting apps, with an event when one goes down or up', enabled: true },
  { name: 'knowledge', description: 'Pages and documents that agents search', enabled: true },
  { name: 'agents', description: "Conversations, memories and pending actions of the org's agents", enabled: true },
  { name: 'integrations', description: 'Tools of the services the org connects, for agents', enabled: true },
  { name: 'accounts', description: 'Accounts that members connect for agents to read', enabled: true },
  { name: 'runpod', description: 'Apps the org deploys to a hosting provider', enabled: true },
];

// The modules on the Explore page, as GET /api/dashboard/<org>/modules returns them. enabled comes from MODULES.
const need = (key, label, connected, extra = {}) => ({ key, label, kind: 'integration', optional: false, connected, ...extra });
const CATALOG = [
  { name: 'knowledge', title: 'Knowledge', description: "Pages and documents that agents search, with crawls on a schedule.", category: 'Storage', switchable: true, needs: [need('embeddings', 'Embeddings service', true, { optional: true }), need('firecrawl', 'Firecrawl', false, { optional: true })], submodules: ['asu'] },
  { name: 'points', title: 'Points', description: "Points, leaderboards and event check-ins.", category: 'Storage', switchable: true, needs: [], submodules: [] },
  { name: 'storefront', title: 'Store', description: "A merch store that members pay for with points.", category: 'Storage', switchable: true, needs: [], submodules: [] },
  { name: 'accounts', title: 'Member accounts', description: "Members connect Canvas, Google and Outlook, and agents read them for the member.", category: 'Storage', switchable: true, needs: [need('ACCOUNTS_BASE_URL', 'ACCOUNTS_BASE_URL setting', true, { kind: 'setting' })], submodules: [] },
  { name: 'agents', title: 'Agent memory', description: "Conversations, memories and pending actions that the org's agents keep for each member, through the API.", category: 'AI and agents', switchable: true, needs: [need('openrouter', 'OpenRouter', false, { optional: true })], submodules: [] },
  { name: 'integrations', title: 'Integration tools', description: "Gives agents the tools of the services that the org connects.", category: 'AI and agents', switchable: true, needs: [], submodules: [] },
  { name: 'feeds', title: 'Feeds', description: 'Posts new internship and new grad roles from GitHub job lists, and upcoming hackathons, to Discord channels.', category: 'Automations', switchable: true, needs: [], submodules: ['careers'] },
  { name: 'calendar', title: 'Calendar sync', description: "Copies Notion events to Google Calendar and the public events feed.", category: 'Automations', switchable: true, needs: [need('notion', 'Notion', false), need('google', 'Google service account', true)], submodules: [] },
  { name: 'uptime', title: 'Uptime', description: "Checks the org's sites and Hosting apps, with an event when one goes down or comes back.", category: 'Automations', switchable: true, needs: [], submodules: [] },
  { name: 'leetcode', title: 'LeetCode', description: "Posts the daily LeetCode question in a Discord channel and checks who solved it.", category: 'Bots', switchable: true, needs: [need('discord', 'Discord bot', true)], submodules: [] },
  { name: 'games', title: 'Games', description: "Jeopardy games in the org's Discord server.", category: 'Bots', switchable: true, needs: [need('discord', 'Discord bot', true)], submodules: [] },
  { name: 'godfather', title: 'Godfather', description: "GPU and CPU pods that members connect to with the Godfather CLI.", category: 'Compute', switchable: true, needs: [need('runpod', 'RunPod', true)], submodules: [] },
  { name: 'runpod', title: 'Hosting', description: "Deploys the org's apps to a hosting provider, and rolls back to an earlier tag.", category: 'Compute', switchable: true, needs: [need('runpod', 'RunPod', true), need('github', 'GitHub', true, { optional: true })], submodules: [] },
];
const CATEGORIES = ['Storage', 'AI and agents', 'Automations', 'Bots', 'Compute'];
const SUBMODULES = {
  asu: { name: 'asu', title: 'Arizona State University', description: 'Public ASU pages and live queries: library hours, events, courses, dining, scholarships, news, shuttles, jobs, sports.' },
  careers: { name: 'careers', title: 'Internships and hackathons', description: 'Alert feeds for software internships, new grad roles and upcoming hackathons.' },
};

// The body of GET /api/dashboard/<org>/modules for the given switch states.
// The limits each module's use counts against (core/limits.py)
const MODULE_LIMITS = {
  knowledge: [
    { key: 'knowledge.sources', label: 'Sources', window: null, paid_by: 'org' },
    { key: 'knowledge.passages', label: 'Passages', window: null, paid_by: 'org' },
    { key: 'knowledge.embeddings_per_day', label: 'Texts embedded a day (knowledge and agent memory)', window: 'day', paid_by: 'metered' },
  ],
  godfather: [{ key: 'godfather.pods', label: 'Pods', window: null, paid_by: 'org' }],
  runpod: [{ key: 'runpod.apps', label: 'Hosting apps', window: null, paid_by: 'org' }],
  uptime: [{ key: 'uptime.monitors', label: 'Uptime monitors', window: null, paid_by: 'org' }],
  alerts: [{ key: 'alerts.destinations', label: 'Alert destinations', window: null, paid_by: 'org' }],
};

export function moduleCatalog(states = MODULES) {
  const enabled = Object.fromEntries(states.map((m) => [m.name, m.enabled]));
  return {
    categories: CATEGORIES,
    modules: CATALOG.map((m) => ({
      ...m,
      enabled: enabled[m.name] ?? true,
      ready: m.needs.every((n) => n.connected || n.optional),
      submodules: m.submodules.map((p) => SUBMODULES[p]),
      limits: MODULE_LIMITS[m.name] ?? [],
    })),
  };
}

// The titles of the modules that need each integration.
const UNLOCKS = CATALOG.flatMap((m) => m.needs.filter((n) => n.kind === 'integration').map((n) => [n.key, m.title]));
const unlocks = (key) => UNLOCKS.filter(([k]) => k === key).map(([, title]) => title).sort();

const SCOPES = {
  'knowledge:read': "Search the organization's knowledge and public sources",
  'knowledge:write': "Write and delete the organization's knowledge sources",
  'agents:read': 'Read conversations, memories and profiles of members the agent talks to',
  'agents:write': 'Write conversations, memories, profiles and pending actions for members',
  'calendar:read': "Read the org's upcoming events",
  'points:read': "Read the org's points leaderboard (names and totals, no emails or student IDs)",
  'apps:read': 'List apps on RunPod, their pods and deployments',
  'apps:deploy': 'Deploy a new image tag of an app',
  'apps:manage': 'Register app manifests and roll apps back',
  'godfather:manage': "List the org's Godfather pods and start, stop, restart or terminate them",
  'org:read': "Read the org's name, description and enabled modules",
  'github:read': "Read the org's GitHub repos, issues, pull requests and Actions runs",
  'github:write': 'Create and change issues, pull requests, comments and files on GitHub (with confirm)',
  'google:read': "Read the org's Google Calendar events, Drive files and Sheets",
  'google:write': 'Create Calendar events and add rows to Sheets (with confirm)',
  'gmail:read': 'Search and read the mail of the Workspace user that Google acts as',
  'gmail:send': 'Send mail as the Workspace user that Google acts as (with confirm)',
  'notion:read': 'Search and read the Notion pages and databases shared with the org\'s integration',
  'notion:write': 'Create Notion pages and database rows (with confirm)',
  'runpod:read': "Read the org's RunPod pods, endpoints, templates, volumes and billing",
  'runpod:write': 'Create, change, start, stop and delete pods and endpoints on RunPod (with confirm)',
  'web:read': "Search the web through the org's SearXNG",
};

const GOOGLE_TOOLS = {
  'google:read': ['google.calendar_events', 'google.calendar_list', 'google.drive_read', 'google.drive_search', 'google.sheets_read'],
  'google:write': ['google.calendar_create_event', 'google.sheets_append'],
  'gmail:read': ['google.gmail_read', 'google.gmail_search'],
  'gmail:send': ['google.gmail_send'],
};

const INTEGRATIONS = [
  { key: 'discord', title: 'Discord', connected: true, scopes: [], through: [], limits: [], used_by: ['bot', 'feeds', 'users'] },
  {
    key: 'embeddings',
    title: 'Embeddings',
    connected: true,
    scopes: [],
    through: ['agents:read', 'agents:write', 'knowledge:read', 'knowledge:write'],
    limits: [],
    used_by: ['agents', 'knowledge'],
  },
  { key: 'firecrawl', title: 'Firecrawl', connected: false, scopes: [], through: ['knowledge:write'], limits: [], used_by: ['knowledge'] },
  {
    key: 'github',
    title: 'GitHub',
    connected: true,
    scopes: ['github:read', 'github:write'],
    through: ['apps:manage'],
    limits: ['repos', 'tools'],
    tools: {},
    remote: true,
  },
  {
    key: 'google',
    title: 'Google',
    connected: true,
    scopes: ['gmail:read', 'gmail:send', 'google:read', 'google:write'],
    through: [],
    limits: [],
    tools: GOOGLE_TOOLS,
  },
  {
    key: 'notion',
    title: 'Notion',
    connected: true,
    scopes: ['notion:read', 'notion:write'],
    through: ['calendar:read'],
    limits: [],
    tools: { 'notion:read': ['notion.query_database', 'notion.read_page', 'notion.search'], 'notion:write': ['notion.create_page'] },
  },
  { key: 'openrouter', title: 'OpenRouter', connected: true, scopes: [], through: [], limits: [], used_by: ['knowledge'] },
  {
    key: 'runpod',
    title: 'RunPod',
    connected: true,
    scopes: ['runpod:read', 'runpod:write'],
    through: ['apps:deploy', 'apps:manage', 'apps:read', 'godfather:manage'],
    limits: [],
    tools: {},
    remote: true,
  },
  {
    key: 'searxng',
    title: 'Web search (SearXNG)',
    connected: false,
    scopes: ['web:read'],
    through: ['knowledge:read'],
    limits: [],
    tools: { 'web:read': ['web.search'] },
  },
];

const SCOPE_USES = {
  'agents:read': ['embeddings'],
  'agents:write': ['embeddings'],
  'knowledge:read': ['embeddings', 'searxng'],
  'knowledge:write': ['embeddings', 'firecrawl'],
  'calendar:read': ['notion'],
  'apps:read': ['runpod'],
  'apps:manage': ['runpod', 'github'],
  'apps:deploy': ['runpod'],
  'godfather:manage': ['runpod'],
};

// All responses, with times relative to now so the dashboard shows "2h ago" and "in 3d".
// 30 days of made-up daily counts. Weekdays are busier, and a few days have failures.
function trends(now) {
  const dates = Array.from({ length: 30 }, (_, i) => new Date(now - (29 - i) * DAY).toISOString().slice(0, 10));
  const series = (key, title, unit, base, spread, failEvery = 0) => {
    const days = dates.map((date, i) => {
      const weekday = new Date(`${date}T00:00:00Z`).getUTCDay();
      const busy = weekday === 0 || weekday === 6 ? 0.4 : 1;
      const value = Math.max(0, Math.round((base + spread * Math.sin(i * 1.7 + key.length)) * busy));
      const failed = failEvery && i % failEvery === 3 && value ? Math.ceil(value / 4) : 0;
      return { date, value, failed };
    });
    const sum = (field) => days.reduce((n, d) => n + d[field], 0);
    return { key, title, unit, total: sum('value'), failed: sum('failed'), days };
  };
  return {
    days: 30,
    generated_at: new Date(now).toISOString(),
    series: [
      series('actions', 'Officer and app actions', 'actions', 14, 8),
      series('jobs', 'Job runs', 'runs', 40, 6, 9),
      series('points', 'Points given', 'points', 60, 45),
      series('orders', 'Store orders', 'orders', 3, 3),
      series('questions', 'Questions to agents', 'questions', 55, 30),
      series('feed_posts', 'Webhook posts', 'posts', 9, 7),
    ],
  };
}

export function fixtures(now = Date.now()) {
  const at = (offset) => new Date(now + offset).toISOString();

  const tokens = [
    {
      id: 11,
      name: 'club-assistant',
      kind: 'agent',
      scopes: ['knowledge:read', 'agents:read', 'agents:write', 'calendar:read', 'github:read'],
      limits: { github: { repos: ['my-org/*'] } },
      display: 'plat_4hQ2',
      created_by: 'officer',
      created_at: at(-40 * DAY),
      expires_at: null,
      last_used_at: at(-3 * MINUTE),
    },
    {
      id: 12,
      name: 'rover-deploy',
      kind: 'app',
      scopes: ['apps:read', 'apps:deploy'],
      display: 'plat_9xLm',
      created_by: 'officer',
      created_at: at(-25 * DAY),
      expires_at: null,
      last_used_at: at(-5 * HOUR),
    },
    {
      id: 13,
      name: 'workshop-helper',
      kind: 'agent',
      scopes: ['knowledge:read', 'points:read'],
      display: 'plat_Tb7c',
      created_by: 'officer',
      created_at: at(-12 * DAY),
      expires_at: null,
      last_used_at: at(-26 * HOUR),
    },
    {
      id: 14,
      name: 'docs-sync',
      kind: 'app',
      scopes: ['knowledge:write'],
      display: 'plat_e2Rw',
      created_by: 'officer',
      created_at: at(-60 * DAY),
      expires_at: null,
      last_used_at: at(-2 * DAY),
    },
  ];

  const audit = (id, offset, action, rest = {}) => ({
    id,
    created_at: at(offset),
    source: 'http',
    action,
    org: 'robotics',
    actor_kind: 'officer',
    actor_id: '1290000000000000101',
    status: 200,
    details: null,
    ...rest,
  });

  const activity = [
    audit(212, -12 * MINUTE, 'PUT /api/organizations/<int:org_id>/modules'),
    audit(211, -48 * MINUTE, 'POST /api/compute/<prefix>/pods/<pod_id>/sessions', { status: 201 }),
    audit(210, -2 * HOUR, 'POST /api/apps/<name>/deploy', { actor_kind: 'token', actor_id: 'rover-deploy', status: 202 }),
    audit(209, -3 * HOUR, 'PUT /api/feeds/<prefix>/feeds/<key>'),
    audit(208, -6 * HOUR, 'POST /api/organizations/<int:org_id>/tokens', { status: 201 }),
    audit(207, -9 * HOUR, 'PUT /api/dashboard/<prefix>/branding'),
    audit(206, -26 * HOUR, 'POST /api/points/<prefix>/import', { status: 201 }),
    audit(205, -2 * DAY, 'PUT /api/organizations/<int:org_id>/secrets/<name>'),
  ];

  const job = (id, offset, name, result) =>
    audit(id, offset, `job ${name}`, { source: 'job', actor_kind: 'job', actor_id: null, status: null, details: { result } });

  const jobs = [
    job(320, -4 * MINUTE, 'feeds.run_feeds', 'posted 3'),
    job(319, -35 * MINUTE, 'godfather.run_schedules', 'started 1 pod'),
    job(318, -61 * MINUTE, 'auth.clean_tokens', 'ran'),
    job(317, -2 * HOUR, 'calendar.sync', 'synced 14 events'),
    job(316, -5 * HOUR, 'knowledge.crawl', 'failed'),
    job(315, -7 * HOUR, 'feeds.run_feeds', 'posted 1'),
  ];

  const pods = [
    { pod_id: '7kq2x9ab', name: 'Workshop GPU (A40)', public: true },
    { pod_id: 'm3v8c1tz', name: 'Rover vision training', public: false },
    { pod_id: 'q9w4e2rd', name: 'Simulation (CPU)', public: false },
  ];

  const sessions = [
    { pod_id: '7kq2x9ab', title: 'Intro to PyTorch', start_at: at(2 * DAY + 3 * HOUR), stop_at: at(2 * DAY + 5 * HOUR) },
    { pod_id: 'q9w4e2rd', title: 'ROS 2 navigation lab', start_at: at(4 * DAY + 2 * HOUR), stop_at: at(4 * DAY + 5 * HOUR) },
    { pod_id: '7kq2x9ab', title: 'Object detection with YOLO', start_at: at(9 * DAY), stop_at: at(9 * DAY + 2 * HOUR) },
    { pod_id: 'm3v8c1tz', title: 'Vision team training run', start_at: at(11 * DAY), stop_at: at(11 * DAY + 8 * HOUR) },
  ];

  // Live pods from GET /api/compute/<org>/pods; machine and costPerHr come from RunPod as is.
  const livePods = [
    {
      id: '7kq2x9ab',
      provider: 'runpod',
      name: 'Workshop GPU (A40)',
      status: 'RUNNING',
      is_public: true,
      allowed_users: [],
      created_by: '1290000000000000101',
      created_at: at(-21 * DAY),
      machine: { gpuTypeId: 'NVIDIA A40', gpuType: { displayName: 'A40' }, location: 'US' },
      cost_per_hour: 0.39,
    },
    {
      id: 'm3v8c1tz',
      provider: 'runpod',
      name: 'Rover vision training',
      status: 'RUNNING',
      is_public: false,
      allowed_users: ['1290000000000000201', '1290000000000000202', '1290000000000000203'],
      created_by: '1290000000000000101',
      created_at: at(-9 * DAY),
      machine: { gpuTypeId: 'NVIDIA GeForce RTX 4090', gpuType: { displayName: 'RTX 4090' }, location: 'CA' },
      cost_per_hour: 0.69,
    },
    {
      id: 'q9w4e2rd',
      provider: 'runpod',
      name: 'Simulation (CPU)',
      status: 'EXITED',
      is_public: false,
      allowed_users: [],
      created_by: '1290000000000000101',
      created_at: at(-3 * DAY),
      machine: { cpuTypeId: 'cpu3c', location: 'US' },
      cost_per_hour: 0.006,
    },
  ];

  const podSessions = [
    { id: 41, pod_id: '7kq2x9ab', title: 'Welcome workshop', start_at: at(-6 * DAY), stop_at: at(-6 * DAY + 2 * HOUR), started: true, finished: true, created_by: '1290000000000000101' },
    { id: 42, pod_id: '7kq2x9ab', title: 'Intro to PyTorch', start_at: at(2 * DAY + 3 * HOUR), stop_at: at(2 * DAY + 5 * HOUR), started: false, finished: false, created_by: '1290000000000000101' },
    { id: 43, pod_id: '7kq2x9ab', title: 'Object detection with YOLO', start_at: at(9 * DAY), stop_at: at(9 * DAY + 2 * HOUR), started: false, finished: false, created_by: '1290000000000000101' },
  ];

  const seconds = (offset) => Math.floor((now + offset) / 1000);
  const podFiles = [
    { name: 'datasets', type: 'directory', size: 4096, modified: seconds(-2 * DAY), permissions: '755' },
    { name: 'notebooks', type: 'directory', size: 4096, modified: seconds(-5 * HOUR), permissions: '755' },
    { name: 'runs', type: 'directory', size: 4096, modified: seconds(-40 * MINUTE), permissions: '755' },
    { name: 'README.md', type: 'file', size: 1832, modified: seconds(-3 * DAY), permissions: '644' },
    { name: 'requirements.txt', type: 'file', size: 214, modified: seconds(-3 * DAY), permissions: '644' },
    { name: 'train.py', type: 'file', size: 6120, modified: seconds(-50 * MINUTE), permissions: '644' },
    { name: 'yolov8n.pt', type: 'file', size: 6_534_387, modified: seconds(-6 * DAY), permissions: '644' },
  ];

  const readme = [
    '# Intro to PyTorch',
    '',
    'Workshop files for the Robotics Club. Everything in /workspace is kept when the pod stops.',
    '',
    '1. pip install -r requirements.txt',
    '2. python train.py --epochs 3',
    '',
  ].join('\n');

  const feeds = [
    {
      key: 'internships',
      kind: 'github_jobs',
      config: { repo: 'example-org/summer-internships', label: 'Internship' },
      every_hours: 3,
      enabled: true,
      destination_id: 5,
      webhook_set: true,
      seeded_at: at(-30 * DAY),
      last_run_at: at(-4 * MINUTE),
      last_error: null,
      posted: 186,
    },
    {
      key: 'hackathons',
      kind: 'hackathons',
      config: {},
      every_hours: 24,
      enabled: true,
      destination_id: 5,
      webhook_set: true,
      seeded_at: at(-30 * DAY),
      last_run_at: at(-7 * HOUR),
      last_error: null,
      posted: 41,
    },
    {
      key: 'new-grad',
      kind: 'github_jobs',
      config: { repo: 'example-org/new-grad-roles', label: 'New grad' },
      every_hours: 6,
      enabled: false,
      destination_id: 5,
      webhook_set: true,
      seeded_at: at(-90 * DAY),
      last_run_at: at(-20 * DAY),
      last_error: null,
      posted: 73,
    },
  ];

  const run = (title, workflow, branch, event, conclusion, offset, status = 'completed') => ({
    workflow,
    branch,
    event,
    status,
    conclusion,
    title,
    url: null,
    started_at: at(offset),
  });

  const ci = {
    repos: [
      {
        repo: 'robotics-club/rover-firmware',
        error: null,
        runs: [
          run('Tune PID gains for the drive motors', 'build', 'main', 'push', 'success', -25 * MINUTE),
          run('Add IMU calibration step', 'build', 'imu-calibration', 'pull_request', null, -6 * MINUTE, 'in_progress'),
        ],
      },
      {
        repo: 'robotics-club/website',
        error: null,
        runs: [run('Update the build season schedule', 'deploy', 'main', 'push', 'success', -3 * HOUR)],
      },
      {
        repo: 'robotics-club/match-scout',
        error: null,
        runs: [run('Bump the model version', 'test', 'main', 'push', 'failure', -9 * HOUR)],
      },
    ],
  };

  const deployment = (id, tag, status, offset, rest = {}) => ({
    id,
    tag,
    status,
    actor: 'token:rover-deploy',
    error: null,
    manifest_ref: null,
    started_at: at(offset),
    finished_at: status === 'deploying' ? null : at(offset + 4 * MINUTE),
    ...rest,
  });

  const telemetryManifest = {
    cloud: 'SECURE',
    disk: 40,
    env: { LOG_LEVEL: 'info' },
    gpu: { count: 1, id: 'NVIDIA RTX A5000' },
    health: { path: '/health', port: 8080 },
    image: 'ghcr.io/robotics-club/rover-telemetry',
    ports: ['8080/http'],
    secret_env: { INFLUX_TOKEN: 'app_rover_influx_token' },
  };

  const telemetryDeployments = [
    deployment(41, 'v1.8.2', 'healthy', -2 * HOUR, { manifest_ref: '9f3c2a1' }),
    deployment(40, 'v1.8.1', 'failed', -26 * HOUR, { manifest_ref: '4be71d0', error: 'The health path did not answer in time', finished_at: at(-26 * HOUR + 15 * MINUTE) }),
    deployment(39, 'v1.8.0', 'healthy', -4 * DAY, { manifest_ref: 'c02d9e4', actor: 'officer:1290000000000000101' }),
    deployment(38, 'v1.7.3', 'healthy', -12 * DAY, { manifest_ref: '71aa5b2' }),
  ];

  const appList = [
    {
      name: 'match-scout',
      kind: 'site',
      description: 'Scouting site for match days',
      url: 'https://scout.robotics.example.org',
      host: 'runpod',
      provider: 'runpod',
      manifest: { cpu: { id: 'cpu5c', vcpuCount: 4 }, health: { path: '/healthz', port: 3000 }, image: 'ghcr.io/robotics-club/match-scout', ports: ['3000/http'] },
      repo: 'robotics-club/match-scout',
      manifest_path: 'deploy/platform.app.yaml',
      pod_id: 'p8d3k2mz',
      current_tag: 'v2.0.0-rc1',
      latest_deployment: deployment(52, 'v2.0.0-rc1', 'deploying', -3 * MINUTE, { manifest_ref: 'e81b7c3' }),
      updated_at: at(-3 * MINUTE),
    },
    {
      name: 'parts-inventory',
      kind: 'service',
      description: null,
      url: null,
      host: 'runpod',
      provider: 'runpod',
      manifest: { cpu: { id: 'cpu3c', vcpuCount: 2 }, health: { path: '/health', port: 8000 }, image: 'ghcr.io/robotics-club/parts-inventory', ports: ['8000/http'] },
      repo: null,
      manifest_path: null,
      pod_id: 'r4n7t1qa',
      current_tag: 'v0.4.0',
      latest_deployment: deployment(33, 'v0.4.0', 'healthy', -6 * DAY, { actor: 'officer:1290000000000000101' }),
      updated_at: at(-6 * DAY),
    },
    {
      name: 'rover-telemetry',
      kind: 'agent',
      description: 'Reads rover telemetry and answers questions in Discord',
      url: null,
      host: 'runpod',
      provider: 'runpod',
      manifest: telemetryManifest,
      repo: 'robotics-club/rover-telemetry',
      manifest_path: 'platform.app.yaml',
      pod_id: 'v6h2w9xe',
      current_tag: 'v1.8.2',
      latest_deployment: telemetryDeployments[0],
      updated_at: at(-2 * HOUR),
    },
  ];

  const telemetryPod = {
    id: 'v6h2w9xe',
    name: 'robotics-rover-telemetry',
    desiredStatus: 'RUNNING',
    image: 'ghcr.io/robotics-club/rover-telemetry:v1.8.2',
    costPerHr: 0.27,
    gpu: { displayName: 'RTX A5000', count: 1 },
    machine: { location: 'US' },
  };

  const preview = (tag) => ({
    dry_run: true,
    tag,
    manifest: telemetryManifest,
    request: {
      method: 'PATCH',
      path: '/pods/v6h2w9xe',
      body: {
        image: `ghcr.io/robotics-club/rover-telemetry:${tag}`,
        env: { LOG_LEVEL: 'info', INFLUX_TOKEN: '(secret)' },
        disk: 40,
        ports: ['8080/http'],
      },
    },
  });

  const crawl = (hours, offset, rest = {}) => ({
    fetch_every_hours: hours,
    extractor: null,
    enabled: true,
    last_attempt_at: at(offset),
    last_error: null,
    ...rest,
  });

  const source = (id, key, category, chunks, offset, rest = {}) => ({
    id: `00000000-0000-4000-8000-0000000000${String(id).padStart(2, '0')}`,
    key,
    url: null,
    title: null,
    category,
    public: false,
    version_id: null,
    content_hash: null,
    embedding_model: 'nomic-embed-text-v1.5',
    chunk_count: chunks,
    fetched_at: offset === null ? null : at(offset),
    updated_at: at(offset ?? -DAY),
    crawl: null,
    ...rest,
  });

  const sources = [
    source(1, 'club/build-nights', 'club', 18, -3 * HOUR, {
      url: 'https://robotics.example.org/build-nights',
      title: 'Build nights',
      crawl: crawl(6, -3 * HOUR),
    }),
    source(2, 'club/faq', 'club', 42, -20 * HOUR, {
      url: 'https://robotics.example.org/faq',
      title: 'Club FAQ',
      crawl: crawl(24, -20 * HOUR),
    }),
    source(3, 'competition/rules-2026', 'competition', 236, -2 * DAY, {
      url: 'https://competition.example.org/2026/game-manual',
      title: 'Game manual 2026',
      crawl: crawl(24, -40 * MINUTE, { last_error: 'The page answered 503 Service Unavailable' }),
    }),
    source(4, 'competition/team-roster', 'competition', 9, -5 * DAY, {
      title: 'Team roster',
    }),
    source(5, 'docs/onboarding', 'docs', 64, -9 * DAY, { title: 'New member onboarding' }),
    source(7, 'upload/sponsor-packet.pdf', 'documents', 31, -6 * HOUR, { title: 'sponsor-packet.pdf' }),
    source(6, 'docs/safety', 'docs', 27, -14 * DAY, {
      url: 'https://robotics.example.org/safety',
      title: 'Shop safety rules',
      crawl: crawl(168, -14 * DAY, { enabled: false }),
    }),
  ];

  const tuning = { chunk_chars: 300, chunk_overlap: 0, mode: 'hybrid', top_k: 8, window: 0, max_distance: 0.6, rrf_k: 60 };
  const knowledgeSettings = {
    settings: { ...tuning, chunk_chars: 600, chunk_overlap: 60, window: 1 },
    defaults: tuning,
    embeddings: {
      configured: true,
      model: 'Qwen3-Embedding-0.6B',
      status: { model: 'Qwen3-Embedding-0.6B', passages: 1840, embedded: 1612, stale: 228, models: [] },
    },
  };
  const knowledgeRun = (id, key, kind, offset, rest = {}) => ({
    id,
    source_key: key,
    kind,
    started_at: at(offset),
    duration_ms: kind === 'upload' ? 2400 : 900,
    changed: false,
    chunks: 18,
    error: null,
    ...rest,
  });
  const knowledgeRuns = [
    knowledgeRun(9, 'club/build-nights', 'crawl', -3 * HOUR, { changed: true }),
    knowledgeRun(8, 'competition/rules-2026', 'crawl', -40 * MINUTE - 3 * HOUR, {
      chunks: null,
      error: 'The page answered 503 Service Unavailable',
    }),
    knowledgeRun(7, 'upload/sponsor-packet.pdf', 'upload', -6 * HOUR, { changed: true, chunks: 31 }),
    knowledgeRun(6, 'upload/scan.pdf', 'upload', -6 * HOUR, {
      chunks: null,
      error: 'The PDF has no text layer. A scanned PDF needs text recognition first',
    }),
    knowledgeRun(5, 'club/faq', 'crawl', -20 * HOUR, { chunks: 42 }),
    knowledgeRun(4, 'docs/onboarding', 'upload', -9 * DAY, { changed: true, chunks: 64 }),
  ];

  const search = {
    dense: true,
    results: [
      {
        chunk_id: 'c1',
        source_key: 'club/build-nights',
        title: 'Build nights',
        url: 'https://robotics.example.org/build-nights',
        category: 'club',
        public: false,
        content: 'Build nights run every Tuesday and Thursday from 6 to 9 pm in the engineering shop, room 120. Bring safety glasses; the club has spares at the door.',
        score: 0.032787,
        fetched_at: at(-3 * HOUR),
      },
      {
        chunk_id: 'c2',
        source_key: 'club/faq',
        title: 'Club FAQ',
        url: 'https://robotics.example.org/faq',
        category: 'club',
        public: false,
        content: 'Do I need experience to join a build night? No. New members pair with a sub-team lead for their first three sessions.',
        score: 0.016129,
        fetched_at: at(-20 * HOUR),
      },
    ],
  };

  // The full text of club/build-nights, as the source page reads it, with the first search result marked.
  const buildNightsText = {
    source: { ...sources[0], content_hash: 'b1d5e0', version_id: 'v1', own: true, text_chars: 2140 },
    passages: [
      ['p0', '# Build nights'],
      ['p1', 'Build nights are open shop hours for every member. Sub-teams use them to build, test and fix the robot between competitions.'],
      ['c1', 'Build nights run every Tuesday and Thursday from 6 to 9 pm in the engineering shop, room 120. Bring safety glasses; the club has spares at the door.'],
      ['p3', '## What to bring\nA laptop with the team repository cloned.\nClosed-toe shoes. The shop does not admit sandals.\nYour shop badge, if you have one.'],
      ['p4', '## First visit\nNew members pair with a sub-team lead for their first three sessions. The lead shows the tools, the parts shelves and the sign-out sheet.'],
      ['p5', '## Power tools\nOnly members with the shop safety sign-off use the drill press, the band saw and the mill. Ask a lead to book the sign-off.'],
      ['p6', 'Parking: lot 59 is free after 5 pm. The shop door locks at 9:15 pm.'],
    ].map(([id, text], ordinal) => ({ id, ordinal, text })),
    focus: ['c1'],
    offset: 0,
    next_offset: null,
    total: 7,
  };

  const overview = {
    organization: { id: ORG.id, name: ORG.name, prefix: ORG.prefix, branding: BRANDING },
    modules: MODULES,
    sections: {
      members: { total: 214 },
      points: { total: 18420, last_30_days: 2310 },
      storefront: { products: 12, pending_orders: 3 },
      godfather: { pods, sessions },
      feeds: {
        feeds: feeds.map((f, i) => ({
          key: f.key,
          kind: f.kind,
          module: 'feeds',
          enabled: f.enabled,
          every_hours: f.every_hours,
          last_run_at: f.last_run_at,
          last_error: f.last_error,
          posted_7_days: [14, 3, 0][i],
        })),
      },
      apps: {
        apps: [
          { name: 'rover-telemetry', provider: 'runpod', repo: 'robotics-club/rover-telemetry', tag: 'v1.8.2', status: 'healthy', deployed_at: at(-2 * HOUR), error: null },
          { name: 'parts-inventory', provider: 'runpod', repo: 'robotics-club/parts-inventory', tag: 'v0.4.0', status: 'healthy', deployed_at: at(-6 * DAY), error: null },
          { name: 'match-scout', provider: 'runpod', repo: 'robotics-club/match-scout', tag: 'v2.0.0-rc1', status: 'deploying', deployed_at: at(-3 * MINUTE), error: null },
        ],
      },
      knowledge: {
        sources: sources.length,
        crawled: sources.filter((x) => x.crawl).length,
        failing: sources.filter((x) => x.crawl?.last_error).map((x) => ({ key: x.key, url: x.url, error: x.crawl.last_error })),
      },
      agents: { conversations: 1290, active_7_days: 342, members_7_days: 87, memories: 2140, pending_actions: 2 },
      accounts: { linked: { google: 41, canvas: 36, microsoft: 12 } },
      tokens: {
        tokens: tokens.map(({ name, kind, scopes, last_used_at }) => ({ name, kind, scopes, last_used_at })),
        cli_tokens: 58,
      },
    },
    problems: [],
    activity,
    jobs,
    generated_at: at(-20 * 1000),
  };

  const notice = (id, module, subject, message, link, resolvedOffset = null) => ({
    id,
    module,
    subject,
    message,
    link,
    kind: 'problem',
    level: 'error',
    at: null,
    resolved_at: resolvedOffset === null ? null : at(resolvedOffset),
    resolved_by: resolvedOffset === null ? null : 'officer:1290000000000000101',
  });
  const event = (id, module, subject, message, link, level, offset) => ({
    ...notice(`event-${id}`, module, subject, message, link),
    kind: 'event',
    level,
    at: at(offset),
  });
  const notifications = [
    event(41, 'errors', 'ReadTimeout', 'Exception on /api/compute/robotics/pods [POST]: Read timed out.', 'activity?tab=errors', 'error', -18 * MINUTE),
    event(40, 'godfather', 'Pod started: workshop-a40', 'By an officer or a tool', 'hosting?tab=pods', 'info', -42 * MINUTE),
    event(39, 'jobs', 'Job failed: knowledge.reindex', 'Embeddings answered 401 Unauthorized', 'activity?tab=knowledge', 'error', -3 * HOUR),
    event(38, 'order', 'New order: Robotics hoodie', 'Member: dana · 450 points', 'store', 'info', -5 * HOUR),
    event(37, 'app', 'Deployed: match-scout v1.4.2', 'Healthy after 38 s', 'hosting?tab=services', 'info', -9 * HOUR),
    notice('a1', 'feeds', 'new-grad', 'The feed answered 404 Not Found', 'job-alerts'),
    notice('k1', 'knowledge', 'club/sponsor-packet', 'sponsors.robotics.example.org does not resolve', 'knowledge'),
    notice('k2', 'knowledge', 'asu/parking_rates', 'The page answered 503 Service Unavailable', 'knowledge'),
    notice('p1', 'apps', 'match-scout', 'Health check failed after 5 tries: GET /health answered 502', 'apps', -2 * HOUR),
  ];

  const field = (name, label, hint, setOffset = null, kind = 'text', more = {}) => ({
    name,
    label,
    hint,
    kind,
    secret: true,
    optional: false,
    set: setOffset !== null,
    value: null,
    updated_at: setOffset === null ? null : at(setOffset),
    ...more,
  });
  const integrations = [
    {
      key: 'discord',
      title: 'Discord',
      description: "Connect the org's Discord server. One Discord app serves every org; the deployment sets it in .env.",
      docs: 'modules/discord-bot',
      fields: [],
      editable: false,
      source: 'deployment',
      testable: true,
      used_by: ['auth', 'leetcode'],
    },
    {
      key: 'embeddings',
      title: 'Embeddings',
      description: 'Connect an OpenAI-compatible embeddings service for meaning search.',
      docs: 'modules/knowledge',
      fields: [
        field('embeddings_url', 'Base URL', 'For example https://openrouter.ai/api/v1, on a public address. Platform adds /embeddings.', -4 * DAY, 'url', {
          secret: false,
          value: 'https://embed.example.org/v1',
        }),
        field('embeddings_model', 'Model', 'A model that returns 1024 numbers, such as Qwen3-Embedding-0.6B, or baai/bge-m3 on OpenRouter.', -4 * DAY, 'text', {
          secret: false,
          value: 'Qwen3-Embedding-0.6B',
        }),
        field('embeddings_api_key', 'API key', 'Leave empty when the service needs no key. For OpenRouter, empty uses the OpenRouter key.', -4 * DAY, 'text', { optional: true }),
        field('embeddings_query_prefix', 'Query prefix', 'Text put before each search query. Qwen3-Embedding takes an instruction here.', null, 'text', {
          secret: false,
          optional: true,
        }),
      ],
      editable: true,
      source: 'org',
      testable: true,
      used_by: ['agents', 'knowledge'],
    },
    {
      key: 'firecrawl',
      title: 'Firecrawl',
      description: 'Connect a Firecrawl server to read pages that need JavaScript.',
      docs: 'modules/knowledge',
      fields: [
        field('firecrawl_url', 'Server URL', 'For example https://api.firecrawl.dev. It must be on a public address.', null, 'url', { secret: false }),
        field('firecrawl_api_key', 'API key', 'Leave empty for a server that needs no key.', null, 'text', { optional: true }),
      ],
      editable: true,
      source: null,
      testable: true,
      used_by: ['knowledge', 'submodules'],
    },
    {
      key: 'github',
      title: 'GitHub',
      description: "Connect the org's GitHub repos with a read-only token.",
      docs: 'modules/runpod-apps',
      fields: [field('github_token', 'Access token', 'A fine-grained token with read access to Actions and Contents.', -9 * DAY)],
      editable: true,
      source: 'org',
      testable: true,
      used_by: ['dashboard', 'runpod'],
    },
    {
      key: 'google',
      title: 'Google',
      description: 'Connect a Google Cloud service account for the org.',
      docs: 'modules/calendar',
      fields: [field('google_service_account', 'Service account key', 'The JSON key of a service account with the Calendar API on.', -30 * DAY, 'json')],
      editable: true,
      source: 'org',
      testable: true,
      used_by: ['calendar'],
    },
    {
      key: 'notion',
      title: 'Notion',
      description: "Connect the org's Notion workspace.",
      docs: 'modules/calendar',
      fields: [field('notion_api_key', 'Integration token', 'Notion > Settings > Integrations.')],
      editable: true,
      source: null,
      testable: true,
      used_by: ['calendar'],
    },
    {
      key: 'openrouter',
      title: 'OpenRouter',
      description: 'Connect an OpenRouter account for hosted models.',
      docs: 'integrations',
      fields: [field('openrouter_api_key', 'API key', 'OpenRouter > Settings > API Keys. Embeddings uses this key when its base URL is OpenRouter.', null)],
      editable: true,
      source: null,
      testable: true,
      used_by: ['agents', 'knowledge'],
    },
    {
      key: 'runpod',
      title: 'RunPod',
      description: "Connect the org's RunPod account.",
      docs: 'modules/godfather',
      fields: [field('runpod_api_key', 'API key', 'RunPod > Settings > API Keys, with read and write access.', -12 * DAY)],
      editable: true,
      source: 'org',
      testable: true,
      used_by: ['godfather', 'runpod'],
    },
    {
      key: 'searxng',
      title: 'Web search (SearXNG)',
      description: 'Connect a SearXNG server for live web search.',
      docs: 'modules/submodules',
      fields: [
        field('searxng_url', 'Server URL', 'A SearXNG server with the json format on, on a public address.', null, 'url', { secret: false }),
        field('searxng_engines', 'Engines', 'Comma-separated. Leave empty for google,brave,bing.', null, 'text', { secret: false, optional: true }),
      ],
      editable: true,
      source: 'deployment',
      testable: true,
      used_by: ['submodules'],
    },
  ];

  const errorGroup = (id, source, org, kind, message, location, route, count, lastOffset, firstOffset, stack = null, context = {}) => ({
    id,
    source,
    org,
    kind,
    message,
    location,
    route,
    stack,
    count,
    first_seen: at(firstOffset),
    last_seen: at(lastOffset),
    resolved_at: null,
    resolved_by: null,
    context,
  });
  const podStack = [
    'Traceback (most recent call last):',
    '  File "modules/godfather/api.py", line 88, in create_pod',
    '    return service.create_pod(db, org, body, actor)',
    '  File "modules/godfather/service.py", line 214, in create_pod',
    '    pod = runpod.create_pod(key, spec)',
    '  File "core/integrations/runpod.py", line 61, in create_pod',
    '    response = requests.post(url, json=spec, timeout=30)',
    '  File "/app/.venv/lib/python3.12/site-packages/requests/api.py", line 115, in post',
    '    return request("post", url, data=data, json=json, **kwargs)',
    '  File "/app/.venv/lib/python3.12/site-packages/requests/adapters.py", line 713, in send',
    '    raise ReadTimeout(e, request=request)',
    'requests.exceptions.ReadTimeout: HTTPSConnectionPool(host=\'rest.runpod.io\', port=443): Read timed out. (read timeout=30)',
  ].join('\n');
  const asuSignedOut = {
    title: 'ASU',
    signed_in: false,
    signed_in_by: null,
    signed_in_at: null,
    expired_at: null,
    blocked: null,
    attempt: null,
  };
  const webhookEvents = [
    ['errors', 'Errors', 'A new error, or a resolved error that comes back. At most 30 messages an hour.', null],
    ['job.failed', 'Failed job runs', 'A background job for the org fails, such as a crawl or a reindex.', null],
    ['pod.started', 'Pods started', 'A pod starts or restarts, by an officer, a tool or its schedule.', 'godfather'],
    ['pod.stopped', 'Pods stopped', 'A pod stops or is terminated, by an officer, a tool or its schedule.', 'godfather'],
    ['app.deployed', 'App deploys', 'An app deploy ends: healthy, or failed with the reason.', null],
    ['order.created', 'Store orders', 'A member places an order in the store.', 'storefront'],
    ['member.joined', 'New members', 'A person joins the org at sign-in, through a form or a CSV import. A Discord member sync does not send it.', null],
    ['knowledge.crawl_failed', 'Knowledge crawl failures', 'A crawl of a knowledge source fails.', null],
    ['monitor.down', 'Monitors down', 'An uptime monitor finds its address down.', 'uptime'],
    ['monitor.up', 'Monitors up', 'An uptime monitor that was down finds its address up again.', 'uptime'],
    ['asu.session_expired', 'ASU sign-in expired', 'The saved ASU sign-in expired. An officer signs in again on the Integrations page.', null],
  ].map(([key, label, description, module]) => ({ key, label, description, module }));
  const webhook = (id, name, hint, events, enabled, lastSent, lastError, created, by) => ({
    id,
    name,
    kind: 'discord',
    url_hint: `discord.com ...${hint}`,
    events,
    enabled,
    last_sent_at: at(lastSent),
    last_error: lastError,
    created_at: at(created),
    created_by: `officer:${by}`,
  });
  const webhooks = [
    webhook(1, 'Errors', '4410', ['errors', 'job.failed', 'knowledge.crawl_failed'], true, -38 * MINUTE, null, -40 * DAY, 'ava'),
    webhook(2, 'Infra', '9027', ['pod.started', 'pod.stopped', 'app.deployed'], true, -2 * HOUR, null, -21 * DAY, 'daniel'),
    webhook(3, 'Store desk', '3315', ['order.created', 'member.joined'], true, -5 * DAY, 'Discord refused the message with status 404', -60 * DAY, 'maya'),
    webhook(4, 'Old ops channel', '7781', ['errors'], false, -45 * DAY, null, -120 * DAY, 'ava'),
    webhook(5, 'Careers', '6120', ['knowledge.crawl_failed'], true, -4 * MINUTE, null, -30 * DAY, 'maya'),
  ];

  // Uptime monitors. down lists the bar slots (0 is the oldest of 30) whose check was down.
  const monitor = (id, name, kind, target, every, enabled, latency, day, week, down = [], error = null) => {
    const recent = Array.from({ length: 30 }, (_, i) => {
      const up = !down.includes(i);
      return {
        checked_at: at(-(29 - i) * every * MINUTE - 20_000),
        up,
        status_code: up ? 200 : error ? 503 : null,
        latency_ms: up ? latency + ((i * 37) % 23) - 11 : null,
        error: up ? null : (error ?? 'No answer in 10 seconds'),
      };
    });
    const last = recent[29];
    return {
      id,
      name,
      target_kind: kind,
      target,
      expected_status: '2xx',
      timeout_seconds: 10,
      interval_minutes: every,
      enabled,
      state: last.up ? 'up' : 'down',
      state_since: at(-(last.up ? 3 * DAY : 4 * every * MINUTE)),
      last_checked_at: last.checked_at,
      last_check: last,
      uptime_24h: day,
      uptime_7d: week,
      recent,
    };
  };
  const monitors = [
    monitor(3, 'Docs site', 'url', 'https://docs.robotics.example.org', 10, false, 98, 100, 100),
    monitor(2, 'Match scout', 'app', 'match-scout', 5, true, 241, 99.31, 99.72, [11, 12]),
    monitor(4, 'Parts inventory API', 'app', 'parts-inventory', 5, true, 310, 97.22, 99.1, [26, 27, 28, 29], 'Status 503, expected 2xx'),
    monitor(5, 'Rover telemetry', 'app', 'rover-telemetry', 1, true, 187, 100, 99.98),
    monitor(1, 'Website', 'url', 'https://robotics.example.org', 5, true, 122, 100, 99.95, [3]),
  ];

  const orgErrors = [
    errorGroup(41, 'api', ORG.prefix, 'ReadTimeout', 'Exception on /api/compute/robotics/pods [POST]: Read timed out. (read timeout=30)', 'core/integrations/runpod.py:create_pod', '/api/compute/<string:org_prefix>/pods', 7, -18 * MINUTE, -2 * DAY, podStack, {
      request: 'POST /api/compute/robotics/pods',
      logger: 'flask.app',
      line: 'modules/godfather/api.py:88',
      release: '2710b68c4f1e',
      host: 'soda-internal-api',
      pid: 7,
      thread: 'ThreadPoolExecutor-0_3',
      python: '3.12.7',
    }),
    errorGroup(39, 'browser', ORG.prefix, 'ApiError', 'Could not reach the API. It may be restarting or have stopped mid-request.', '/robotics/hosting (mutation)', '/robotics/hosting (mutation)', 4, -26 * MINUTE, -1 * DAY),
    errorGroup(35, 'api', ORG.prefix, 'KeyError', "Error in sync_members: 'guild_id'", 'modules/users/service.py:sync_discord_members', '/api/users/<string:org_prefix>/discord/sync', 3, -3 * HOUR, -3 * HOUR),
    errorGroup(30, 'bot', ORG.prefix, 'HTTPException', '403 Forbidden (error code: 50013): Missing Permissions', 'modules/leetcode/service.py:post_daily', null, 2, -9 * HOUR, -2 * DAY),
  ];
  const serverErrors = [
    errorGroup(22, 'worker', null, 'OperationalError', 'job failed name=knowledge.crawl_due: database is locked', 'core/jobs.py:_execute', null, 26, -2 * DAY, -9 * DAY),
  ];

  const secret = (name, description, setOffset) => ({
    name,
    description,
    set: setOffset !== null,
    updated_at: setOffset === null ? null : at(setOffset),
    updated_by: setOffset === null ? null : '1290000000000000101',
  });

  const detail = (org, rest = {}) => ({
    description: null,
    is_active: true,
    config: {},
    created_at: at(-200 * DAY),
    updated_at: at(-3 * DAY),
    officer_role_id: null,
    points_per_message: 1,
    points_cooldown: 60,
    google_calendar_id: null,
    notion_database_id: null,
    calendar_sync_enabled: false,
    last_sync_at: null,
    ...org,
    ...rest,
  });

  const orgDetail = detail(ORG, {
    description: 'Builds rovers, drones and competition robots. Weekly build nights and workshops.',
    officer_role_id: '1290000000000000201',
    points_per_message: 2,
    points_cooldown: 120,
    google_calendar_id: 'robotics-events@group.calendar.google.com',
    notion_database_id: '9f3c2a1b7d5e4c8a9b0e1f2a3b4c5d6e',
    last_sync_at: at(-2 * HOUR),
  });

  const otherOrgs = [
    detail(
      { id: 2, name: 'Data Science Club', prefix: 'datasci', guild_id: '1290000000000000300', icon_url: null },
      { officer_role_id: '1290000000000000301' },
    ),
    detail({ id: 3, name: 'Game Dev Guild', prefix: 'gamedev', guild_id: '1290000000000000400', icon_url: null }),
    detail(
      { id: 4, name: 'Chess Society', prefix: 'chess', guild_id: '1290000000000000500', icon_url: null },
      { is_active: false, officer_role_id: '1290000000000000501' },
    ),
  ];

  const role = (id, name, position) => ({ id, name, color: 0, position, permissions: '0' });

  const crossAudit = [
    audit(402, -5 * MINUTE, 'PUT /api/superadmin/update_officer_role/<int:org_id>', { org: null }),
    audit(401, -25 * MINUTE, 'PUT /api/organizations/<int:org_id>/settings', { org: 'datasci' }),
    ...activity.slice(0, 3),
    audit(204, -4 * HOUR, 'POST /api/points/<prefix>/import', { org: 'gamedev', status: 201 }),
    ...jobs.slice(0, 2),
  ].sort((a, b) => b.created_at.localeCompare(a.created_at));

  // Points: members with totals, and the entries the totals come from.
  const people = [
    ['Ada Park', 'ada.park@example.edu', true],
    ['Bruno Silva', 'bruno.silva@example.edu', true],
    ['Chen Wei', 'chen.wei@example.edu', true],
    ['Dana Ortiz', 'dana.ortiz@example.edu', false],
    ['Eli Novak', 'eli.novak@example.edu', true],
    ['Farah Haddad', 'farah.haddad@example.edu', true],
    ['Gus Moreno', 'gus.moreno@example.edu', false],
    ['Hana Sato', 'hana.sato@example.edu', true],
  ];
  const awards = [
    ['Build night', 10, -2 * DAY, [0, 1, 2, 4, 5, 7]],
    ['Robot demo day', 25, -9 * DAY, [0, 2, 3, 5]],
    ['Intro to ROS workshop', 15, -16 * DAY, [0, 1, 4, 6, 7]],
    ['Soldering workshop', 10, -23 * DAY, [1, 2, 3]],
    ['Regional competition', 50, -40 * DAY, [0, 2, 5]],
  ];
  const pointEntries = [];
  for (const [event, points, offset, who] of awards) {
    for (const i of who) {
      pointEntries.push({
        id: pointEntries.length + 1,
        points,
        event,
        awarded_by_officer: event === 'Robot demo day' ? 'CSV Upload' : 'officer',
        timestamp: at(offset + i * MINUTE),
        last_updated: at(offset + i * MINUTE),
        user_id: 100 + i,
        organization_id: ORG.id,
      });
    }
  }
  pointEntries.push({
    id: pointEntries.length + 1,
    points: -40,
    event: 'Storefront Purchase - Order #41',
    awarded_by_officer: 'System',
    timestamp: at(-5 * DAY),
    last_updated: at(-5 * DAY),
    user_id: 100,
    organization_id: ORG.id,
  });
  const members = people.map(([name, email, linked], i) => ({
    id: 100 + i,
    uuid: `5b1f0c2e-0000-4000-8000-00000000010${i}`,
    name,
    username: email.split('@')[0],
    email,
    major: null,
    discord_linked: linked,
    points: pointEntries.filter((e) => e.user_id === 100 + i).reduce((n, e) => n + e.points, 0),
    joined_at: at(-(60 + i * 7) * DAY),
    created_at: at(-(60 + i * 7) * DAY),
  }));
  const pointsHistory = Object.fromEntries(
    members.map((m) => [
      `/api/points/${ORG.prefix}/users/${encodeURIComponent(m.email)}/points`,
      {
        user: { id: m.id, name: m.name, email: m.email, username: m.username },
        organization: { name: ORG.name, prefix: ORG.prefix },
        total_points: m.points,
        points_history: pointEntries
          .filter((e) => e.user_id === m.id)
          .sort((a, b) => b.timestamp.localeCompare(a.timestamp))
          .map(({ id, points, event, awarded_by_officer, timestamp, last_updated }) => ({
            id,
            points,
            event,
            awarded_by_officer,
            timestamp,
            last_updated,
          })),
      },
    ]),
  );

  // Store: products and the orders members placed.
  const product = (id, name, category, price, stock, updated) => ({
    id,
    name,
    description: null,
    price,
    stock,
    image_url: null,
    category,
    organization_id: ORG.id,
    created_at: at(-90 * DAY),
    updated_at: at(updated),
  });
  const products = [
    product(1, 'Club hoodie', 'Apparel', 250, 14, -3 * DAY),
    product(2, 'Rover sticker submodule', 'Stickers', 20, 120, -12 * DAY),
    product(3, 'Arduino starter kit', 'Hardware', 180, 0, -1 * DAY),
    product(4, 'Competition T-shirt', 'Apparel', 120, 32, -20 * DAY),
    product(5, 'Servo motor', 'Hardware', 40, 25, -6 * DAY),
  ];
  const order = (id, who, status, offset, items, message = null) => ({
    id,
    user_id: 100 + who,
    total_amount: items.reduce((n, [pid, qty]) => n + products[pid - 1].price * qty, 0),
    status,
    message,
    created_at: at(offset),
    updated_at: at(offset + HOUR),
    organization_id: ORG.id,
    user_name: people[who][0],
    user_email: people[who][1],
    items: items.map(([pid, qty], i) => ({
      id: id * 10 + i,
      product_id: pid,
      quantity: qty,
      price_at_time: products[pid - 1].price,
    })),
  });
  const orders = [
    order(44, 2, 'pending', -3 * HOUR, [
      [1, 1],
      [2, 2],
    ]),
    order(43, 5, 'processing', -1 * DAY, [[5, 2]], 'Pick up at the Thursday build night.'),
    order(42, 7, 'pending', -2 * DAY, [[4, 1]]),
    order(41, 0, 'delivered', -5 * DAY, [[2, 2]], 'Picked up.'),
    order(40, 1, 'cancelled', -11 * DAY, [[3, 1]]),
  ];

  // Calendar: upcoming events from the Notion database. An event with only a date lasts all day.
  const calendarEvents = [
    { id: 'n-1', title: 'Build night', start: at(2 * DAY), end: at(2 * DAY + 3 * HOUR), location: 'Engineering Center, room 210' },
    { id: 'n-2', title: 'Intro to CAD workshop', start: at(5 * DAY), end: at(5 * DAY + 2 * HOUR), location: 'Library makerspace' },
    { id: 'n-3', title: 'General meeting', start: at(8 * DAY), end: at(8 * DAY + HOUR), location: 'Student union, ballroom B' },
    { id: 'n-4', title: 'Rover field test', start: at(12 * DAY).slice(0, 10) },
    { id: 'n-5', title: 'Build night', start: at(9 * DAY), end: at(9 * DAY + 3 * HOUR), location: 'Engineering Center, room 210' },
  ];

  // Per-org limits (core/limits.py): [key, module, label, unit, window, default, used by each org]
  const limitSpecs = [
    ['agents.conversations', 'agents', 'Agent conversations', 'conversations', null, 5000, [1290, 310, 0]],
    ['agents.memories', 'agents', 'Agent memories', 'memories', null, 20000, [2140, 860, 0]],
    ['alerts.destinations', 'alerts', 'Alert destinations', 'destinations', null, 20, [5, 0, 1]],
    ['godfather.pods', 'godfather', 'Pods', 'pods', null, 10, [4, 9, 0]],
    ['knowledge.embeddings_per_day', 'knowledge', 'Texts embedded a day (knowledge and agent memory)', 'texts', 'day', 500000, [12840, 431200, 0]],
    ['knowledge.jobs_per_day', 'knowledge', 'Crawls, re-indexes and re-embeds started by hand a day', 'jobs', 'day', 200, [6, 41, 0]],
    ['knowledge.passages', 'knowledge', 'Passages', 'passages', null, 250000, [18420, 236900, 0]],
    ['knowledge.sources', 'knowledge', 'Sources', 'sources', null, 1000, [212, 880, 0]],
    ['knowledge.uploads_per_day', 'knowledge', 'Files uploaded a day', 'files', 'day', 500, [4, 12, 0]],
    ['mcp.calls_per_minute', 'mcp', 'Tool calls a minute (MCP and /api/tools)', 'calls', 'minute', 300, [18, 120, 2]],
    ['runpod.apps', 'runpod', 'Hosting apps', 'apps', null, 25, [5, 2, 0]],
    ['uptime.monitors', 'uptime', 'Uptime monitors', 'monitors', null, 50, [8, 3, 0]],
  ];
  const limitCatalog = limitSpecs.map(([key, module, label, unit, window, value]) => ({
    key,
    module,
    label,
    unit,
    window,
    default: value,
    paid_by: window ? 'metered' : 'org',
    integrations: key === 'knowledge.embeddings_per_day' ? ['embeddings'] : [],
  }));
  const overridesFor = [{ 'godfather.pods': 12 }, { 'knowledge.sources': 1200, 'mcp.calls_per_minute': null }, {}];
  const offFor = [new Set(), new Set(['runpod']), new Set(['knowledge', 'godfather', 'runpod'])];
  const limitRows = (i) =>
    limitSpecs.map(([key, module, label, unit, window, value, used], n) => {
      const override = key in overridesFor[i];
      return { ...limitCatalog[n], value: override ? overridesFor[i][key] : value, override, used: used[i], enabled: !offFor[i].has(module) };
    });
  const orgLimits = [orgDetail, ...otherOrgs.slice(0, 2)].map((o, i) => {
    const limits = limitRows(i);
    const near = limits.filter((r) => r.enabled && r.value !== null && r.used >= 0.8 * Math.max(r.value, 1)).map((r) => r.key);
    const overrides = Object.entries(overridesFor[i]).map(([key, value]) => ({ key, value, updated_at: at(-3 * DAY), updated_by: 'superadmin:1290000000000000999' }));
    return { org: { id: o.id, name: o.name, prefix: o.prefix, is_active: true }, limits, near, overrides };
  });
  const GB = 1024 ** 3;
  // Submodules: ASU shared by 3 orgs and subscribed here; careers not subscribed
  const sharedSubmodules = [
    {
      name: 'asu',
      title: 'Arizona State University',
      description: 'Public ASU pages and live queries: library hours, events, courses, dining, scholarships, news, shuttles, jobs, sports.',
      key_prefix: 'asu/',
      pages: 226,
      queries: ['courses', 'course_catalog', 'scholarships', 'events', 'news', 'dining', 'web'],
      feeds: [],
      parts: [
        { kind: 'pages', count: 226, paid_by: 'shared', module: 'knowledge' },
        { kind: 'queries', count: 7, paid_by: 'org', module: 'knowledge' },
      ],
      sources: 226,
      last_crawl: at(-40 * MINUTE),
      subscribed: true,
      subscribers: 3,
      modules: ['accounts', 'knowledge'],
    },
    {
      name: 'careers',
      title: 'Internships and hackathons',
      description: 'Feeds of software internships, new grad roles and hackathons.',
      key_prefix: 'careers/',
      pages: 0,
      queries: [],
      feeds: ['internships', 'new-grad', 'hackathons'],
      parts: [{ kind: 'feeds', count: 3, paid_by: 'org', module: 'feeds' }],
      sources: 0,
      last_crawl: null,
      subscribed: true,
      subscribers: 2,
      modules: ['feeds'],
    },
  ];

  return {
    '/api/organizations/': [ORG],
    [`/api/organizations/${ORG.id}/limits`]: { limits: orgLimits[0].limits.filter((r) => r.enabled) },
    '/api/superadmin/limits': { catalog: limitCatalog, near: 0.8, orgs: orgLimits },
    '/api/superadmin/server': {
      cpus: 2,
      load: [0.42, 0.37, 0.31],
      uptime_seconds: 41 * 24 * 3600,
      memory: { total: 7.75 * GB, available: 4.9 * GB },
      disk: { total: 96 * GB, used: 48 * GB, free: 48 * GB },
      database_bytes: 1.1 * 1024 ** 2,
      database: 'sqlite',
      container: { memory_used: 0.29 * GB, memory_limit: 1.5 * GB, cpu_limit: 1.5, process_uptime_seconds: 5 * 3600 + 12 * 60 },
      bot_ready: true,
      jobs: { backend: 'inline', queue: null },
    },
    '/api/superadmin/server/services': {
      agent: { age_seconds: 12, stale: false },
      services: [
        ['platform-api', 'container', 0.23 * GB, 1.5 * GB, [8000], ['api.example.org'], 'platform', null, false],
        ['platform-dashboard', 'container', 0.02 * GB, 0.25 * GB, [5001], ['admin.example.org'], 'platform', null, false],
        ['proxy', 'container', 0.1 * GB, null, [81], ['proxy.example.org'], 'infrastructure', null, true],
        ['vaultwarden', 'container', 0.04 * GB, null, [8081], ['vault.robotics.example.org'], 'org', orgDetail, true],
        ['crm_server', 'container', 0.49 * GB, null, [2020], ['crm.robotics.example.org'], 'org', orgDetail, true],
        ['website', 'process', 0.08 * GB, null, [3002], ['robotics.example.org'], null, null, false],
        ['old-site', 'container', null, null, [], [], null, null, false],
      ].map(([name, kind, used, limit, ports, domains, owner, org, set]) => ({
        name,
        kind,
        state: used == null ? 'created' : 'running',
        status: used == null ? 'Created' : 'Up 2 weeks',
        image: null,
        project: null,
        memory_used: used,
        memory_limit: limit,
        cpu_percent: used == null ? null : 0.4,
        ports,
        domains,
        owner,
        org: org ? { id: org.id, name: org.name, prefix: org.prefix } : null,
        set,
      })),
    },
    [`/api/organizations/${ORG.id}`]: orgDetail,
    [`/api/organizations/${ORG.id}/calendar`]: {
      notion_database_id: orgDetail.notion_database_id,
      google_calendar_id: orgDetail.google_calendar_id,
      calendar_sync_enabled: false,
      last_sync_at: orgDetail.last_sync_at,
    },
    [`/api/organizations/${ORG.id}/leetcode`]: {
      settings: { channel_id: '1290000000000000777', role_ping: '1290000000000000778', daily_time: '09:00' },
      enabled: true,
    },
    '/api/superadmin/check': { is_superadmin: true },
    '/api/superadmin/dashboard': {
      available_guilds: [
        { id: '1290000000000000600', name: 'Hackathon Team', icon: { url: null } },
        { id: '1290000000000000700', name: 'Photography Club', icon: { url: null } },
      ],
      existing_orgs: [orgDetail, ...otherOrgs],
      officer_orgs: [orgDetail],
    },
    [`/api/superadmin/guild_roles/${ORG.guild_id}`]: {
      roles: [
        role('1290000000000000200', 'Admin', 5),
        role('1290000000000000201', 'Officer', 4),
        role('1290000000000000202', 'Project lead', 3),
        role('1290000000000000203', 'Member', 1),
      ],
    },
    '/api/superadmin/audit': { entries: crossAudit },
    '/api/superadmin/publishers': { publishers: [{ org_id: orgDetail.id, prefix: orgDetail.prefix, source: 'superadmin' }] },
    [`/api/dashboard/${ORG.prefix}/branding`]: BRANDING,
    [`/api/dashboard/${ORG.prefix}/overview`]: overview,
    [`/api/dashboard/${ORG.prefix}/modules`]: moduleCatalog(),
    [`/api/dashboard/${ORG.prefix}/integrations`]: {
      integrations: integrations.map((i) => ({ ...i, metered_by: i.metered_by ?? [], unlocks: unlocks(i.key) })),
      oauth: {
        notion: { title: 'Notion', connected: true, connected_by: 'ash', connected_at: at(-2 * DAY), blocked: null },
        google: { title: 'Google', connected: false, connected_by: null, connected_at: null, blocked: null },
      },
      secrets_key: true,
    },
    [`/api/dashboard/${ORG.prefix}/submodules/asu/signin`]: asuSignedOut,
    [`/api/dashboard/${ORG.prefix}/notifications`]: { notifications, open: notifications.filter((n) => !n.resolved_at).length },
    [`/api/dashboard/${ORG.prefix}/ci`]: ci,
    [`/api/dashboard/${ORG.prefix}/errors`]: { errors: orgErrors, open: orgErrors.length, events: orgErrors.reduce((n, e) => n + e.count, 0), webhook_set: true },
    '/api/superadmin/errors': { errors: [...orgErrors, ...serverErrors].sort((a, b) => b.last_seen.localeCompare(a.last_seen)) },
    [`/api/feeds/${ORG.prefix}/feeds`]: { feeds },
    [`/api/uptime/${ORG.prefix}/monitors`]: { monitors },
    [`/api/uptime/${ORG.prefix}/targets`]: { apps: appList.map((a) => ({ name: a.name, url: a.url })) },
    [`/api/dashboard/${ORG.prefix}/webhooks`]: {
      webhooks,
      events: webhookEvents,
      kinds: [{ key: 'discord', label: 'Discord', example: 'https://discord.com/api/webhooks/...' }],
      feeds: feeds.map(({ key, kind, enabled, destination_id, webhook_set, last_run_at, last_error }) => ({ key, kind, enabled, destination_id, webhook_set, last_run_at, last_error })),
      secrets_key: true,
    },
    ...Object.fromEntries(
      webhooks.map((w) => [`/api/dashboard/${ORG.prefix}/webhooks/${w.id}/test`, { ok: true, message: 'Sent. Look for the message in the channel.' }]),
    ),
    [`/api/feeds/${ORG.prefix}/presets`]: {
      presets: [
        {
          module: 'feeds',
          submodule: 'careers',
          submodule_title: 'Internships and hackathons',
          key: 'new-grad',
          title: 'New grad roles',
          description: 'New rows in the 2026 new grad list that vanshb03 keeps on GitHub.',
          kind: 'github_jobs',
          config: { repo: 'vanshb03/New-Grad-2026', branch: 'main', path: 'README.md', label: 'New grad', skip_closed: true, max_age_days: 2 },
          every_hours: 3,
          added: false,
        },
      ],
    },
    [`/api/organizations/${ORG.id}/tokens`]: { tokens, scopes: SCOPES, integrations: INTEGRATIONS, uses: SCOPE_USES },
    [`/api/organizations/${ORG.id}/audit`]: { entries: [...activity, ...jobs].sort((a, b) => b.id - a.id) },
    [`/api/organizations/${ORG.id}/modules`]: { modules: MODULES },
    [`/api/dashboard/${ORG.prefix}/hosting/providers`]: { providers: [{ name: 'runpod', title: 'RunPod', integration: 'runpod', configured: true }] },
    [`/api/dashboard/${ORG.prefix}/apps`]: { apps: appList },
    [`/api/dashboard/${ORG.prefix}/apps/rover-telemetry`]: { ...appList[2], deployments: telemetryDeployments },
    [`/api/dashboard/${ORG.prefix}/apps/rover-telemetry/pod`]: { pod: telemetryPod },
    [`/api/dashboard/${ORG.prefix}/apps/rover-telemetry/deploy`]: preview('v1.9.0'),
    [`/api/dashboard/${ORG.prefix}/apps/rover-telemetry/rollback`]: preview('v1.8.0'),
    [`/api/dashboard/${ORG.prefix}/submodules`]: { submodules: sharedSubmodules },
    [`/api/dashboard/${ORG.prefix}/knowledge/submodules`]: { submodules: sharedSubmodules },
    [`/api/dashboard/${ORG.prefix}/knowledge/sources`]: { sources, can_publish: false },
    [`/api/dashboard/${ORG.prefix}/knowledge/search`]: search,
    [`/api/dashboard/${ORG.prefix}/knowledge/sources/club/build-nights`]: buildNightsText,
    [`/api/dashboard/${ORG.prefix}/knowledge/settings`]: knowledgeSettings,
    [`/api/dashboard/${ORG.prefix}/knowledge/runs`]: { runs: knowledgeRuns },
    [`/api/dashboard/${ORG.prefix}/trends`]: trends(now),
    [`/api/compute/${ORG.prefix}/pods`]: { pods: livePods },
    [`/api/compute/${ORG.prefix}/settings`]: {
      settings: { pod_image: 'theaisocietyasu/workshop-base:latest', deployment_pod_image: 'ghcr.io/theaisocietyasu/godfather-base:latest' },
    },
    ...Object.fromEntries(
      livePods.map((pod) => [
        `/api/compute/${ORG.prefix}/pods/${pod.id}/sessions`,
        { sessions: podSessions.filter((s) => s.pod_id === pod.id) },
      ]),
    ),
    [`/api/compute/${ORG.prefix}/members`]: {
      members: [
        ['Ava Chen', 'avachen'],
        ['Daniel Ortiz', 'dortiz'],
        ['Maya Patel', 'mayap'],
        ['Noah Kim', 'noahk'],
        ['Priya Singh', 'priya.s'],
        ['Sam Rivera', 'samr'],
      ].map(([name, username], i) => ({ id: String(410000000000000000n + BigInt(i)), name, username, avatar: null })),
      total: 214,
    },
    [`/api/users/${ORG.prefix}/discord/sync`]: { matched: 214, new_users: 171, joined: 188, already: 26 },
    [`/api/users/${ORG.prefix}/discord/roles`]: {
      roles: [
        { id: '1200', name: 'Officers', color: '#e67e22' },
        { id: '1201', name: 'GPU workshop', color: '#3498db' },
        { id: '1202', name: 'Members', color: '#2ecc71' },
      ],
    },
    [`/api/compute/${ORG.prefix}/pods/m3v8c1tz/members`]: {
      pod_id: 'm3v8c1tz',
      access: {
        is_public: false,
        allowed: [
          { discord_id: '1290000000000000201', name: 'Maya Patel' },
          { discord_id: '1290000000000000202', name: 'Noah Kim' },
          { discord_id: '1290000000000000203', name: null },
        ],
      },
      recent: [
        ['1290000000000000201', 'Maya Patel', 'mayap', false, -25 * MINUTE],
        ['1290000000000000101', 'Ava Chen', 'avachen', true, -70 * MINUTE],
        ['1290000000000000202', 'Noah Kim', 'noahk', false, -5 * HOUR],
        ['1290000000000000201', 'Maya Patel', 'mayap', false, -DAY - 3 * HOUR],
        ['1290000000000000202', 'Noah Kim', 'noahk', false, -3 * DAY],
      ].map(([discord_id, name, username, is_admin, offset]) => ({ discord_id, name, username, is_admin, created_at: at(offset) })),
    },
    [`/api/compute/${ORG.prefix}/pods/m3v8c1tz/members/connected`]: {
      pod_id: 'm3v8c1tz',
      state: 'known',
      reason: null,
      sessions: [
        { username: 'mayap', is_admin: false, seconds: 1500, discord_id: '1290000000000000201', name: 'Maya Patel' },
        { username: 'avachen', is_admin: true, seconds: 640, discord_id: '1290000000000000101', name: 'Ava Chen' },
      ],
    },
    [`/api/compute/${ORG.prefix}/pods/7kq2x9ab/members`]: { pod_id: '7kq2x9ab', access: { is_public: true, allowed: [] }, recent: [] },
    [`/api/compute/${ORG.prefix}/pods/7kq2x9ab/members/connected`]: {
      pod_id: '7kq2x9ab',
      state: 'unknown',
      reason: 'The pod image has no godfather-login, so its sessions cannot be read',
      sessions: [],
    },
    [`/api/compute/${ORG.prefix}/pods/7kq2x9ab/files`]: { path: '/workspace', files: podFiles },
    [`/api/compute/${ORG.prefix}/pods/7kq2x9ab/files/read`]: { path: '/workspace/README.md', content: readme },

    [`/api/points/${ORG.prefix}/users`]: {
      organization: { name: ORG.name, prefix: ORG.prefix, description: orgDetail.description },
      total_users: members.length,
      users: members,
    },
    [`/api/points/${ORG.prefix}/get_points`]: pointEntries,
    ...pointsHistory,
    [`/api/storefront/${ORG.prefix}/products`]: products,
    [`/api/storefront/${ORG.prefix}/orders`]: orders,
    [`/api/calendar/${ORG.prefix}/events`]: {
      status: 'success',
      organization_id: ORG.id,
      organization_name: ORG.name,
      events: calendarEvents,
      total_events: calendarEvents.length,
    },

    [`/api/organizations/${ORG.id}/secrets`]: {
      configured: true,
      secrets: [
        secret('github_token', "GitHub token that can read the contents of the org's private app repos", -8 * DAY),
        secret('google_service_account', "Google service account key (JSON) that owns this org's calendar", -30 * DAY),
        secret('notion_api_key', "Notion integration token for this org's events database", -30 * DAY),
        secret('runpod_api_key', "RunPod API key the org's apps are deployed and billed with", -45 * DAY),
      ],
    },
  };
}

// The same org with long lists, for perf.mjs: 2,000 knowledge sources, 1,500 members, 200 knowledge runs,
// 600 store orders and 1,000 audit log entries.
// The ASU sign-in while Duo shows a code, for the asu-duo screenshot.
export function asuDuoFixtures(now = Date.now()) {
  const data = fixtures(now);
  const path = `/api/dashboard/${ORG.prefix}/submodules/asu/signin`;
  const asu = {
    ...data[path],
    attempt: {
      state: 'duo_code',
      message: 'Enter the code 482916 in the Duo app.',
      code: '482916',
      reason: null,
      started_at: new Date(now - 20_000).toISOString(),
      finished_at: null,
    },
  };
  return { ...data, [path]: asu };
}

export function largeFixtures(now = Date.now()) {
  const base = fixtures(now);
  const at = (offset) => new Date(now + offset).toISOString();
  const domains = ['asu', 'club', 'competition', 'docs', 'events', 'upload'];
  const words = ['library', 'hours', 'dining', 'shuttle', 'robot', 'rules', 'faq', 'safety', 'workshop', 'sponsor', 'news'];
  const word = (i) => words[i % words.length];
  const sources = Array.from({ length: 2000 }, (_, i) => {
    const domain = domains[i % domains.length];
    const crawled = i % 3 !== 0;
    const fetched = at(-((i % 72) + 1) * HOUR);
    return {
      id: `00000000-0000-4000-9000-${String(i).padStart(12, '0')}`,
      key: `${domain}/${word(i)}-${word(i * 7 + 3)}-${i}`,
      url: crawled ? `https://${domain}.example.org/${word(i)}/${i}` : null,
      title: `${word(i)} ${word(i + 5)} ${i}`,
      category: domain === 'upload' ? 'documents' : domain,
      public: i % 17 === 0,
      version_id: null,
      content_hash: null,
      embedding_model: 'nomic-embed-text-v1.5',
      chunk_count: (i * 37) % 300,
      fetched_at: fetched,
      updated_at: fetched,
      crawl: crawled
        ? {
            fetch_every_hours: [6, 24, 168][i % 3],
            extractor: null,
            enabled: i % 11 !== 0,
            last_attempt_at: fetched,
            last_error: i % 29 === 0 ? 'The page answered 503 Service Unavailable' : null,
          }
        : null,
    };
  });
  const first = ['Ana', 'Ben', 'Chloe', 'Dev', 'Eli', 'Farah', 'Gus', 'Hana', 'Ivan', 'Jade', 'Kofi', 'Lena', 'Milo'];
  const last = ['Ruiz', 'Okafor', 'Park', 'Shah', 'Novak', 'Haddad', 'Moreno', 'Sato', 'Petrov', 'Lin', 'Mensah'];
  const members = Array.from({ length: 1500 }, (_, i) => {
    const name = `${first[i % first.length]} ${last[(i * 5) % last.length]} ${i}`;
    const username = name.toLowerCase().replaceAll(' ', '.');
    return {
      id: 1000 + i,
      uuid: `5b1f0c2e-0000-4000-9000-${String(i).padStart(12, '0')}`,
      name,
      username,
      email: `${username}@example.edu`,
      major: null,
      discord_linked: i % 4 !== 0,
      points: (i * 53) % 900,
      joined_at: at(-((i % 400) + 1) * DAY),
      created_at: at(-((i % 400) + 1) * DAY),
    };
  });
  const runs = Array.from({ length: 200 }, (_, i) => ({
    id: 10_000 - i,
    source_key: sources[i * 7].key,
    kind: i % 5 === 0 ? 'upload' : 'crawl',
    started_at: at(-(i + 1) * 20 * MINUTE),
    duration_ms: 400 + ((i * 97) % 5000),
    changed: i % 3 === 0,
    chunks: i % 13 === 0 ? null : (i * 11) % 200,
    error: i % 13 === 0 ? 'The page answered 503 Service Unavailable' : null,
  }));
  const products = base[`/api/storefront/${ORG.prefix}/products`];
  const statuses = ['pending', 'processing', 'shipped', 'delivered', 'cancelled'];
  const orders = Array.from({ length: 600 }, (_, i) => {
    const m = members[(i * 13) % members.length];
    const p = products[i % products.length];
    const qty = (i % 3) + 1;
    return {
      id: 5000 - i,
      user_id: m.id,
      total_amount: p.price * qty,
      status: statuses[i % statuses.length],
      message: null,
      created_at: at(-(i + 1) * 3 * HOUR),
      updated_at: at(-(i + 1) * 3 * HOUR),
      organization_id: ORG.id,
      user_name: m.name,
      user_email: m.email,
      items: [{ id: i, product_id: p.id, quantity: qty, price_at_time: p.price }],
    };
  });
  const actions = ['PUT /api/organizations/<int:org_id>/modules', 'POST /api/points/<prefix>/import', 'job knowledge.crawl'];
  const audit = Array.from({ length: 1000 }, (_, i) => ({
    id: 90_000 - i,
    created_at: at(-(i + 1) * 30 * MINUTE),
    source: i % 3 === 2 ? 'job' : 'http',
    action: actions[i % 3],
    org: ORG.prefix,
    actor_kind: i % 3 === 2 ? 'job' : 'officer',
    actor_id: i % 3 === 2 ? null : '1290000000000000101',
    status: i % 3 === 2 ? null : 200,
    details: i % 3 === 2 ? { result: i % 20 === 2 ? 'failed' : 'ok' } : null,
  }));
  const users = base[`/api/points/${ORG.prefix}/users`];
  return {
    ...base,
    [`/api/dashboard/${ORG.prefix}/knowledge/sources`]: { sources, can_publish: false },
    [`/api/dashboard/${ORG.prefix}/knowledge/runs`]: { runs },
    [`/api/points/${ORG.prefix}/users`]: { ...users, total_users: members.length, users: members },
    [`/api/storefront/${ORG.prefix}/orders`]: orders,
    [`/api/organizations/${ORG.id}/audit`]: { entries: audit },
  };
}
