// Records the product demo video of the dashboard for the hero of site/, with every API call answered from
// fixtures.ts. Run with npm run demo-video. Needs ffmpeg and Chromium for Playwright (npx playwright install chromium),
// or PLAYWRIGHT_CHROMIUM set to a Chromium binary.
//
// The script works in two passes:
// 1. Record: a director drives the built dashboard at 1440x900 with real clicks and key presses. It keeps a
//    video clock of its own and takes a screenshot each time the UI changes. It also writes down where the
//    pointer goes, where the camera looks and which caption shows, each at a time on the video clock.
// 2. Render: a second page draws each video frame from that timeline: the app window on a soft background,
//    the camera zoom, the pointer, click ripples and captions. ffmpeg encodes the frames.
// The video clock does not depend on how fast the machine is, so frames are never dropped or doubled.
//
// Output: ../site/public/demo/platform-demo.mp4, platform-demo.webm and poster.webp.
// DEMO_FPS sets the frame rate (default 30). DEMO_WORK sets the folder for the screenshots and the master file.
// PLAYWRIGHT_CHROMIUM sets the Chromium binary when the installed browser does not match the Playwright version.

import { execSync, spawn } from 'node:child_process';
import { copyFileSync, mkdirSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { chromium } from 'playwright';
import type { Browser, Locator, Page, Route } from 'playwright';
import { preview } from 'vite';
import { BRANDING, fixtures, ORG } from './fixtures.ts';
import type { Branding, PodSession, Source } from './fixtures.ts';

declare global {
  interface Window {
    // Draws one video frame. The script of the compositor page sets it.
    apply: (state: FrameState) => Promise<void>;
  }
}

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const out = resolve(root, process.env.DEMO_OUT ?? '../site/public/demo');
const work = resolve(process.env.DEMO_WORK ?? join(tmpdir(), 'platform-demo'));
const FPS = Number(process.env.DEMO_FPS ?? 30);
const PORT = 4181;
const BASE = `http://localhost:${PORT}`;

// The app viewport in CSS pixels, and the device scale of its screenshots.
const VIEW = { width: 1440, height: 900 };
const SCALE = 2;
// The video frame. The app window shows the viewport at K output pixels per CSS pixel when the camera is at zoom 1.
const OUT = { width: 1600, height: 1000 };
const K = 0.9;
const BAR = 36;
const WIN = { x: (OUT.width - VIEW.width * K) / 2, y: 38, width: VIEW.width * K, height: VIEW.height * K + BAR };
// The caption sits under the window. The camera keeps a zoomed element above it.
const CAPTION_Y = 942;
const SAFE_CENTER_Y = 452;
const MAX_ZOOM = 1.9;
// The video plays the recorded timeline this many times faster. The closing card plays at normal speed.
const WARP = Number(process.env.DEMO_WARP ?? 1.35);

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
const clamp01 = (v: number) => clamp(v, 0, 1);
const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
const easeInOut = (p: number) => (p < 0.5 ? 4 * p * p * p : 1 - (-2 * p + 2) ** 3 / 2);
const easeCamera = (p: number) => p * p * p * (p * (p * 6 - 15) + 10);

// A small seeded random source, so the typing rhythm is the same on each run.
function random(seed: number) {
  let s = seed;
  return () => {
    s = (s * 1664525 + 1013904223) % 4294967296;
    return s / 4294967296;
  };
}

// ---------------------------------------------------------------------------------------------------------------
// The API: fixtures.ts plus the state changes the story makes, such as a module that turns on or a new token.

// The JSON bodies that the dashboard sends to the routes that the story calls.
interface RequestBody {
  modules?: Record<string, boolean>;
  logo_url?: string;
  accent_color?: string;
  website_url?: string;
  user_identifier?: string;
  points?: number;
  event?: string;
  ids?: string[];
  fields?: Record<string, string>;
  title?: string | null;
  start_at?: string;
  stop_at?: string;
  dry_run?: boolean;
  tag?: string;
  name?: string;
  kind?: string;
  scopes?: string[];
}

interface HandlerResult {
  status?: number;
  json?: unknown;
  redirect?: string;
}

type Handler = (body: RequestBody | null, match: RegExpMatchArray) => HandlerResult;

function demoApi() {
  const now = Date.now();
  const at = (offset = 0) => new Date(Date.now() + offset).toISOString();
  const data = fixtures(now);
  // The same object, for paths that fixtures() does not have or builds from a list.
  const routes: Record<string, unknown> = data;
  const P = ORG.prefix;
  const ID = ORG.id;
  const overview = data[`/api/dashboard/${P}/overview`];

  // The org starts with points off and no accent color. The story turns both on.
  const modules = data[`/api/organizations/${ID}/modules`].modules.map((m) => ({ ...m, enabled: m.name === 'points' ? false : m.enabled }));
  data[`/api/organizations/${ID}/modules`] = { modules };
  overview.modules = modules;
  const branding: Branding = { ...BRANDING, accent_color: null };
  data[`/api/dashboard/${P}/branding`] = branding;
  overview.organization.branding = branding;

  // The officer of the story has the officer role in three orgs and is not the superadmin.
  data['/api/organizations/'] = [
    ORG,
    { id: 2, name: 'Data Science Club', prefix: 'datasci', guild_id: '1290000000000000300', icon_url: null },
    { id: 3, name: 'Game Dev Guild', prefix: 'gamedev', guild_id: '1290000000000000400', icon_url: null },
  ];
  data['/api/superadmin/check'] = { is_superadmin: false };

  routes[`/api/feeds/${P}/feeds/internships/history`] = {
    runs: [
      { started_at: at(-4 * 60_000), duration_ms: 1800, found: 412, new: 3, posted: 3, recorded: false, error: null },
      { started_at: at(-3 * 3_600_000), duration_ms: 1600, found: 409, new: 2, posted: 2, recorded: false, error: null },
      { started_at: at(-6 * 3_600_000), duration_ms: 2100, found: 407, new: 0, posted: 0, recorded: false, error: null },
      { started_at: at(-9 * 3_600_000), duration_ms: 1700, found: 407, new: 4, posted: 4, recorded: false, error: null },
    ],
    items: [
      { title: 'Robotics Software Intern - Northwind Robotics', posted: true, created_at: at(-4 * 60_000) },
      { title: 'Embedded Systems Intern - Example Aerospace', posted: true, created_at: at(-4 * 60_000) },
      { title: 'Computer Vision Intern - Contoso Labs', posted: true, created_at: at(-4 * 60_000) },
      { title: 'Firmware Engineering Intern - Fabrikam Motors', posted: true, created_at: at(-3 * 3_600_000) },
    ],
  };

  const auditList = data[`/api/organizations/${ID}/audit`].entries;
  let auditId = 300;
  const record = (action: string, status = 200) => {
    const entry = {
      id: auditId++,
      created_at: at(),
      source: 'http',
      action,
      org: P,
      actor_kind: 'officer',
      actor_id: '1290000000000000101',
      status,
      details: null,
    };
    auditList.unshift(entry);
    overview.activity.unshift(entry);
  };

  const sources = data[`/api/dashboard/${P}/knowledge/sources`].sources;
  const runs = data[`/api/dashboard/${P}/knowledge/runs`].runs;
  const newSource = (key: string, rest: Partial<Source>): Source => ({
    id: `00000000-0000-4000-8000-0000000001${String(sources.length).padStart(2, '0')}`,
    key,
    url: null,
    title: null,
    category: 'club',
    public: false,
    version_id: null,
    content_hash: null,
    embedding_model: 'nomic-embed-text-v1.5',
    chunk_count: 0,
    fetched_at: null,
    updated_at: at(),
    crawl: null,
    ...rest,
  });

  const tokenList = data[`/api/organizations/${ID}/tokens`].tokens;
  const deployments = data[`/api/dashboard/${P}/apps/rover-telemetry`].deployments;

  // Each handler answers one method and path pattern. A non-GET request with no handler gets an empty 200.
  const handlers: [method: string, pattern: RegExp, handle: Handler][] = [
    ['GET', /^\/api\/auth\/login$/, () => ({ redirect: `${BASE}/auth?code=demo` })],
    ['POST', /^\/api\/auth\/exchange$/, () => ({ json: { access_token: 'demo-access', refresh_token: 'demo-refresh' } })],
    [
      'PUT',
      new RegExp(`^/api/organizations/${ID}/modules$`),
      (body) => {
        for (const [name, on] of Object.entries(body?.modules ?? {})) {
          const m = modules.find((x) => x.name === name);
          if (m) m.enabled = Boolean(on);
        }
        record('PUT /api/organizations/<int:org_id>/modules');
        return { json: { modules } };
      },
    ],
    [
      'PUT',
      new RegExp(`^/api/dashboard/${P}/branding$`),
      (body) => {
        branding.logo_url = body?.logo_url || null;
        branding.accent_color = body?.accent_color || null;
        branding.website_url = body?.website_url || null;
        record('PUT /api/dashboard/<prefix>/branding');
        return { json: branding };
      },
    ],
    [
      'POST',
      new RegExp(`^/api/points/${P}/assign_points$`),
      (body) => {
        const users = data[`/api/points/${P}/users`].users;
        const member = users.find((u) => u.email === body?.user_identifier || u.username === body?.user_identifier);
        if (!member || !body) return { status: 404, json: { error: 'No member with that email or username' } };
        member.points += body.points ?? 0;
        const entries = data[`/api/points/${P}/get_points`];
        entries.push({
          id: entries.length + 1,
          points: body.points ?? 0,
          event: body.event ?? '',
          awarded_by_officer: 'officer',
          timestamp: at(),
          last_updated: at(),
          user_id: member.id,
          organization_id: ID,
        });
        record('POST /api/points/<prefix>/assign_points', 201);
        return { status: 201, json: { message: 'Points awarded' } };
      },
    ],
    [
      'POST',
      new RegExp(`^/api/dashboard/${P}/knowledge/documents$`),
      () => {
        const file = 'build-season-handbook.pdf';
        sources.unshift(newSource(`upload/${file}`, { title: file, category: 'documents', chunk_count: 48, fetched_at: at() }));
        runs.unshift({ id: 10, source_key: `upload/${file}`, kind: 'upload', started_at: at(), duration_ms: 2600, changed: true, chunks: 48, error: null });
        record('POST /api/dashboard/<prefix>/knowledge/documents', 201);
        return { status: 201, json: { indexed: 1, unchanged: 0, failed: 0, files: [{ file, key: `upload/${file}`, changed: true, chunks: 48, error: null }] } };
      },
    ],
    [
      'POST',
      new RegExp(`^/api/dashboard/${P}/knowledge/submodules/asu/sync$`),
      () => {
        data[`/api/dashboard/${P}/knowledge/submodules`].submodules[0].sources = 46;
        record('POST /api/dashboard/<prefix>/knowledge/submodules/<name>/sync');
        return { json: { added: 46, updated: 0, retired: 0 } };
      },
    ],
    [
      'POST',
      new RegExp(`^/api/dashboard/${P}/notifications/resolve$`),
      (body) => {
        const list = data[`/api/dashboard/${P}/notifications`];
        for (const n of list.notifications) {
          if ((body?.ids ?? []).includes(n.id)) Object.assign(n, { resolved_at: at(), resolved_by: '1290000000000000101' });
        }
        list.open = list.notifications.filter((n) => !n.resolved_at).length;
        overview.problems = overview.problems?.filter((p) => !(body?.ids ?? []).includes(p.id));
        record('POST /api/dashboard/<prefix>/notifications/resolve');
        return { json: list };
      },
    ],
    [
      'PUT',
      new RegExp(`^/api/dashboard/${P}/integrations/([a-z]+)$`),
      (body, match) => {
        const list = data[`/api/dashboard/${P}/integrations`];
        const entry = list.integrations.find((i) => i.key === match[1]);
        for (const f of entry?.fields ?? []) {
          if (body?.fields?.[f.name]) Object.assign(f, { set: true, updated_at: at() });
        }
        if (entry) entry.source = 'org';
        record('PUT /api/dashboard/<prefix>/integrations/<key>');
        return { json: list };
      },
    ],
    [
      'POST',
      new RegExp(`^/api/dashboard/${P}/integrations/([a-z]+)/test$`),
      () => ({ json: { ok: true, message: 'Connected as Robotics Club Bot.' } }),
    ],
    ['POST', new RegExp(`^/api/dashboard/${P}/knowledge/search$`), () => ({ json: data[`/api/dashboard/${P}/knowledge/search`] })],
    [
      'POST',
      new RegExp(`^/api/compute/${P}/pods/([^/]+)/sessions$`),
      (body, match) => {
        const path = `/api/compute/${P}/pods/${match[1]}/sessions`;
        const list = (routes[path] as { sessions: PodSession[] }).sessions;
        const session: PodSession = {
          id: 50 + list.length,
          pod_id: match[1],
          title: body?.title ?? null,
          start_at: body?.start_at ?? '',
          stop_at: body?.stop_at ?? '',
          started: false,
          finished: false,
          created_by: '1290000000000000101',
        };
        list.push(session);
        list.sort((a, b) => a.start_at.localeCompare(b.start_at));
        overview.sections.godfather.sessions.push({ pod_id: match[1], title: session.title, start_at: session.start_at, stop_at: session.stop_at });
        record('POST /api/compute/<prefix>/pods/<pod_id>/sessions', 201);
        return { status: 201, json: { session } };
      },
    ],
    [
      'POST',
      new RegExp(`^/api/dashboard/${P}/apps/rover-telemetry/deploy$`),
      (body) => {
        if (body?.dry_run) return { json: data[`/api/dashboard/${P}/apps/rover-telemetry/deploy`] };
        const deployment = {
          id: 53,
          tag: body?.tag ?? '',
          status: 'deploying',
          actor: 'officer:1290000000000000101',
          error: null,
          manifest_ref: '9f3c2a1',
          started_at: at(),
          finished_at: null,
        };
        deployments.unshift(deployment);
        data[`/api/dashboard/${P}/apps/rover-telemetry`].latest_deployment = deployment;
        record('POST /api/dashboard/<prefix>/apps/<name>/deploy', 202);
        return { status: 202, json: { deployment } };
      },
    ],
    [
      'POST',
      new RegExp(`^/api/organizations/${ID}/tokens$`),
      (body) => {
        tokenList.unshift({
          id: 15,
          name: body?.name ?? '',
          kind: body?.kind ?? '',
          scopes: body?.scopes ?? [],
          display: 'plat_7Qm2',
          created_by: 'officer',
          created_at: at(),
          expires_at: null,
          last_used_at: null,
        });
        record('POST /api/organizations/<int:org_id>/tokens', 201);
        return { status: 201, json: { token: 'plat_7Qm2hX9cLw4pT1vZ8nBy3KdR6sFj0aEu' } };
      },
    ],
  ];

  return async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin === BASE) return route.fallback();
    let body: RequestBody | null = null;
    try {
      body = request.postDataJSON();
    } catch {
      body = null;
    }
    for (const [method, pattern, handle] of handlers) {
      const match = request.method() === method && url.pathname.match(pattern);
      if (!match) continue;
      const result = handle(body, match);
      if (result.redirect) return route.fulfill({ status: 302, headers: { location: result.redirect } });
      return route.fulfill({ status: result.status ?? 200, json: result.json });
    }
    if (request.method() !== 'GET') return route.fulfill({ status: 200, json: {} });
    const found = routes[url.pathname];
    if (found === undefined) return route.fulfill({ status: 404, json: { error: `No fixture for ${url.pathname}` } });
    return route.fulfill({ status: 200, json: found });
  };
}

// ---------------------------------------------------------------------------------------------------------------
// The director: drives the app and writes the timeline. Points are in app CSS pixels unless a name says scene.

interface Point {
  x: number;
  y: number;
}

interface Box extends Point {
  width: number;
  height: number;
}

// What the pointer moves to or the camera zooms on: a CSS selector, a locator or a box in app pixels.
type Target = string | Locator | Box;

interface Camera {
  z: number;
  fx: number;
  fy: number;
}

interface CameraMove extends Camera {
  t: number;
  dur: number;
  from: Camera;
}

interface Shot {
  t: number;
  file: string;
  fade: number;
  title: string;
}

interface Move {
  t0: number;
  t1: number;
  a: Point;
  b: Point;
  c: Point;
}

interface Caption {
  text: string;
  keys: string[] | null;
  t0: number;
  t1: number | null;
}

interface Drag {
  t0: number;
  t1: number | null;
  label: string;
}

interface ClickOptions {
  after?: number;
  fade?: number;
  offset?: Point;
  animate?: number;
  hover?: boolean;
}

const toScene = (p: Point) => ({ x: WIN.x + p.x * K, y: WIN.y + BAR + p.y * K });

class Director {
  page: Page;
  t: number;
  shots: Shot[];
  moves: Move[];
  clicks: (Point & { t: number })[];
  captions: Caption[];
  drags: Drag[];
  cams: CameraMove[];
  pointer: Point;
  rand: () => number;
  count: number;

  constructor(page: Page) {
    this.page = page;
    this.t = 0;
    this.shots = [];
    this.moves = [];
    this.clicks = [];
    this.captions = [];
    this.drags = [];
    this.cams = [];
    this.pointer = { x: VIEW.width * 0.7, y: VIEW.height * 0.92 };
    this.rand = random(7);
    this.count = 0;
    mkdirSync(join(work, 'shots'), { recursive: true });
  }

  // The camera at time t, in scene pixels.
  camAt(t: number) {
    let cam: Camera = { z: 1, fx: OUT.width / 2, fy: OUT.height / 2 };
    for (const k of this.cams) {
      if (k.t > t) break;
      const e = easeCamera(clamp01((t - k.t) / k.dur));
      cam = { z: Math.exp(lerp(Math.log(k.from.z), Math.log(k.z), e)), fx: lerp(k.from.fx, k.fx, e), fy: lerp(k.from.fy, k.fy, e) };
    }
    return cam;
  }

  // Moves the camera to zoom z on a scene point over dur seconds, from the current time. It does not wait.
  camera(z: number, sceneX: number, sceneY: number, dur = 0.75) {
    const halfW = OUT.width / (2 * z);
    const halfH = OUT.height / (2 * z);
    const fx = clamp(sceneX, halfW, OUT.width - halfW);
    const fy = clamp(sceneY + (OUT.height / 2 - SAFE_CENTER_Y) / z, halfH, OUT.height - halfH);
    this.cams.push({ t: this.t, dur, z, fx, fy, from: this.camAt(this.t) });
  }

  // Zooms on a box (app pixels), as far as it fits in the frame and at most max.
  async zoomTo(target: Target, { max = 1.6, pad = 1.18, dur = 0.75, dx = 0, dy = 0 } = {}) {
    const b = await this.box(target);
    const z = clamp(Math.min(OUT.width / (b.width * K * pad), (OUT.height - 140) / (b.height * K * pad), max), 1, MAX_ZOOM);
    const c = toScene({ x: b.x + b.width / 2 + dx, y: b.y + b.height / 2 + dy });
    this.camera(z, c.x, c.y, dur);
  }

  zoomOut(dur = 0.75) {
    this.camera(1, OUT.width / 2, OUT.height / 2, dur);
  }

  async box(target: Target): Promise<Box> {
    if (typeof target === 'object' && 'width' in target) return target;
    const loc = typeof target === 'string' ? this.page.locator(target).first() : target.first();
    await loc.waitFor({ state: 'visible', timeout: 8000 });
    const b = await loc.boundingBox();
    if (!b) throw new Error(`No box for ${target}`);
    return b;
  }

  caption(text: string, keys: string[] | null = null) {
    const last = this.captions.at(-1);
    if (last && last.t1 === null) last.t1 = this.t;
    this.captions.push({ text, keys, t0: this.t + 0.05, t1: null });
  }

  endCaption() {
    const last = this.captions.at(-1);
    if (last && last.t1 === null) last.t1 = this.t;
  }

  hold(seconds: number) {
    this.t += seconds;
  }

  // Waits for the UI to settle: no loading skeletons, then a short pause for the last render.
  async settle(ms = 180) {
    await this.page
      .waitForFunction(() => !document.querySelector('.animate-pulse, [aria-label="Loading"]'), null, { timeout: 6000 })
      .catch(() => {});
    await this.page.waitForTimeout(ms);
  }

  // Takes a screenshot that shows from the current time, with a cross-fade of fade seconds from the one before.
  async shot(fade = 0.14, { settle = true } = {}) {
    if (settle) await this.settle();
    const file = join(work, 'shots', `${String(this.count++).padStart(4, '0')}.png`);
    await this.page.screenshot({ path: file, type: 'png', caret: 'initial' });
    const title = await this.page.title();
    this.shots.push({ t: this.t, file, fade, title });
  }

  // Glides the pointer to a target on an eased curve. With real false the app mouse does not move.
  async glide(target: Target | Point, { real = true, offset = { x: 0, y: 0 }, speed = 1, hover = true } = {}) {
    let to: Point;
    if (typeof target === 'object' && 'x' in target && !('width' in target)) to = target;
    else {
      const b = await this.box(target);
      to = { x: b.x + b.width / 2 + offset.x, y: b.y + b.height / 2 + offset.y };
    }
    const from = this.pointer;
    const dist = Math.hypot(to.x - from.x, to.y - from.y);
    if (dist < 2) return to;
    const dur = clamp(0.5 + dist / 2400, 0.55, 0.78) / speed;
    // The curve bends to one side by a part of the distance, so the path is not a straight line.
    const bend = (this.rand() < 0.5 ? -1 : 1) * clamp(dist * 0.12, 8, 70);
    const nx = -(to.y - from.y) / dist;
    const ny = (to.x - from.x) / dist;
    const ctrl = { x: (from.x + to.x) / 2 + nx * bend, y: (from.y + to.y) / 2 + ny * bend };
    this.moves.push({ t0: this.t, t1: this.t + dur, a: from, b: to, c: ctrl });
    this.t += dur;
    this.pointer = to;
    if (real && to.x >= 0 && to.y >= 0 && to.x < VIEW.width && to.y < VIEW.height) {
      await this.page.mouse.move(to.x, to.y);
      if (hover) await this.shot(0.12);
    }
    return to;
  }

  // Clicks a target: glides to it, shows a ripple and clicks the app at the same point.
  async click(target: Target | null, { after = 0.3, fade = 0.16, offset, animate = 0, hover = true }: ClickOptions = {}) {
    const to = target ? await this.glide(target, { offset, hover }) : this.pointer;
    this.hold(0.08);
    this.clicks.push({ t: this.t, ...to });
    const act = () => this.page.mouse.click(to.x, to.y);
    if (animate) await this.animated(act, animate);
    else {
      await act();
      this.hold(0.06);
      await this.shot(fade);
    }
    this.hold(after);
  }

  // Types text key by key with a natural rhythm. Each key press gets its own screenshot.
  async type(text: string, { cps = 22 } = {}) {
    for (const ch of text) {
      await this.page.keyboard.type(ch);
      await this.shot(0, { settle: false });
      this.t += (1 / cps) * (0.65 + this.rand() * 0.7) * (ch === ' ' ? 1.3 : 1);
    }
    await this.settle(80);
  }

  async press(key: string, { animate = 0, fade = 0.16, after = 0.25 } = {}) {
    const act = () => this.page.keyboard.press(key);
    if (animate) await this.animated(act, animate);
    else {
      await act();
      await this.shot(fade);
    }
    this.hold(after);
  }

  // Runs an action with motion on and takes one screenshot per frame while its CSS transitions play.
  // The transitions are paused and moved forward by the video clock, so their speed does not depend on capture time.
  async animated(action: () => Promise<void>, ms = 220) {
    await this.page.emulateMedia({ reducedMotion: 'no-preference' });
    await action();
    const frames = Math.ceil((ms / 1000) * FPS);
    for (let i = 1; i <= frames; i++) {
      const now = (i * 1000) / FPS;
      await this.page.evaluate((ms) => {
        for (const a of document.getAnimations()) {
          a.pause();
          a.currentTime = ms;
        }
      }, now);
      this.t += 1 / FPS;
      await this.shot(0, { settle: false });
    }
    await this.page.evaluate(() => {
      for (const a of document.getAnimations()) {
        const timing = a.effect?.getComputedTiming();
        if (timing && timing.iterations !== Infinity) a.finish();
        else a.play();
      }
    });
    await this.page.emulateMedia({ reducedMotion: 'reduce' });
    await this.settle(120);
    await this.shot(0.1);
  }

  // Scrolls the page (or an element) to y over dur seconds, one screenshot per frame.
  async scroll(y: number, { dur = 0.8, within = null }: { dur?: number; within?: string | null } = {}) {
    const read = (sel: string | null) => {
      const el = (sel ? document.querySelector(sel) : document.scrollingElement)!;
      return { top: el.scrollTop, max: el.scrollHeight - el.clientHeight };
    };
    const start = await this.page.evaluate(read, within);
    const target = clamp(y, 0, start.max);
    const frames = Math.max(1, Math.round(dur * FPS));
    for (let i = 1; i <= frames; i++) {
      const top = lerp(start.top, target, easeInOut(i / frames));
      await this.page.evaluate(({ sel, top }) => {
        const el = (sel ? document.querySelector(sel) : document.scrollingElement)!;
        el.scrollTop = top;
      }, { sel: within, top });
      this.t += 1 / FPS;
      await this.shot(0, { settle: false });
    }
    await this.settle(100);
  }

  // The page scroll position that puts the top of a target margin pixels under the top bar.
  async scrollTarget(target: string | Locator, margin = 64) {
    const loc = typeof target === 'string' ? this.page.locator(target).first() : target.first();
    return loc.evaluate((el, m) => el.getBoundingClientRect().top + window.scrollY - m, margin);
  }

  drag(label: string) {
    this.drags.push({ t0: this.t, t1: null, label });
  }

  endDrag() {
    const last = this.drags.at(-1);
    if (last && last.t1 === null) last.t1 = this.t;
  }
}

// ---------------------------------------------------------------------------------------------------------------
// The story: one officer sets up and uses Platform for the Robotics Club.

async function story(d: Director) {
  const page = d.page;
  const nav = (label: string) => page.getByRole('navigation', { name: 'Pages' }).getByRole('link', { name: label, exact: true });
  const dialog = () => page.locator('dialog[open]');
  const card = (heading: string) => page.getByRole('heading', { name: heading }).locator('xpath=ancestor::div[contains(@class,"rounded")][1]');
  const P = ORG.prefix;

  // Sign in with Discord, then pick the org.
  await page.goto(`${BASE}/login`);
  await d.shot(0);
  d.hold(0.5);
  d.caption('Sign in with Discord');
  const signIn = page.getByRole('link', { name: 'Continue with Discord' });
  await d.zoomTo(signIn.locator('xpath=..'), { max: 1.75 });
  d.hold(0.2);
  await d.click(signIn, { after: 0.1 });
  await page.waitForURL(`${BASE}/`);
  await d.shot(0.18);
  d.caption('Pick your org');
  await d.zoomTo(page.getByRole('heading', { name: 'Choose an org' }).locator('xpath=..'), { max: 1.6 });
  await d.click(page.getByRole('link', { name: /Robotics Club/ }), { after: 0.05 });
  await page.waitForURL(`${BASE}/${P}`);
  d.zoomOut();

  // The overview.
  d.caption('See your org at a glance');
  await d.shot(0.18);
  d.hold(0.5);
  await d.glide({ x: 900, y: 330 }, { real: false });
  await d.zoomTo(card('Modules'), { max: 1.45, dx: 120 });
  d.hold(0.7);
  d.zoomOut();

  // Notifications: the bell, then resolve one.
  d.caption('Resolve what needs attention');
  const bell = page.getByRole('button', { name: /^Notifications/ });
  await d.click(bell, { animate: 200, after: 0.05 });
  const panel = page.getByRole('dialog', { name: 'Notifications' });
  await d.zoomTo(panel, { max: 1.6, dx: -120 });
  await d.click(panel.getByRole('button', { name: 'Resolve', exact: true }).first(), { after: 0.6 });
  d.zoomOut();
  await d.press('Escape', { animate: 180, after: 0.05 });

  // Settings: branding, then modules.
  await d.click(nav('Settings'), { after: 0.1 });
  d.caption("Set your org's colors");
  await d.scroll(await d.scrollTarget('#branding'), { dur: 0.6 });
  await d.zoomTo('#branding', { max: 1.55 });
  await d.click(page.getByPlaceholder('#1f6feb'), { after: 0.05 });
  await d.type('#2563eb', { cps: 16 });
  await d.click(page.getByRole('button', { name: 'Save branding' }), { after: 0.35 });

  d.caption('Turn on the modules your org uses');
  d.zoomOut(0.7);
  await d.scroll(await d.scrollTarget('#modules'), { dur: 0.6 });
  await d.zoomTo('#modules', { max: 1.5, dx: 260 });
  await d.click(page.getByRole('switch', { name: 'points', exact: true }), { after: 0.3 });
  d.zoomOut();

  // Integrations: connect Notion, then test it.
  await d.click(nav('Integrations'), { after: 0.1 });
  d.caption('Connect Notion, Google and RunPod');
  const notion = card('Notion');
  await d.zoomTo(notion, { max: 1.5 });
  await d.click(notion.getByRole('button', { name: 'Connect' }), { animate: 180, after: 0.05 });
  await d.zoomTo(dialog(), { max: 1.5 });
  await d.click(dialog().locator('input').first(), { after: 0.05 });
  await d.type('ntn_4f9a2c81b7', { cps: 30 });
  await d.click(dialog().getByRole('button', { name: 'Save' }), { animate: 180, after: 0.2 });
  await d.zoomTo(card('Notion'), { max: 1.5 });
  await d.click(card('Notion').getByRole('button', { name: 'Test' }), { after: 0.7 });
  d.zoomOut();

  // Points: the leaderboard, then points for an event.
  await d.click(nav('Points'), { after: 0.2 });
  d.caption('Give members points for events');
  await d.click(page.getByRole('button', { name: 'Award points' }), { animate: 180, after: 0.05 });
  await d.zoomTo(dialog(), { max: 1.55 });
  await d.click(dialog().getByPlaceholder('ada@example.edu'), { after: 0.05 });
  await d.type('ada.park@example.edu', { cps: 34 });
  await d.click(dialog().getByPlaceholder('10'), { after: 0.05 });
  await d.type('15');
  await d.click(dialog().getByPlaceholder('Build night'), { after: 0.05 });
  await d.type('Rover demo night', { cps: 30 });
  await d.click(dialog().getByRole('button', { name: 'Award points' }), { after: 0.1 });
  d.zoomOut();
  await d.click(page.getByRole('tab', { name: 'Events' }), { animate: 180, after: 0.1 });
  await d.zoomTo(page.locator('main table').first(), { max: 1.4 });
  d.hold(0.8);
  d.zoomOut();

  // Store.
  await d.click(nav('Store'), { after: 0.1 });
  d.caption('Sell merch for points');
  d.hold(0.5);
  await d.click(page.getByRole('tab', { name: /Orders/ }), { animate: 180, after: 0.1 });
  await d.zoomTo(page.locator('main table').first(), { max: 1.35 });
  d.hold(0.7);
  d.zoomOut();

  // Webhooks and bots: job alerts and LeetCode.
  await d.click(nav('Job alerts'), { after: 0.1 });
  d.caption('Post job and hackathon alerts to Discord');
  await d.click(page.getByRole('button', { name: 'History of internships' }), { animate: 180, after: 0.05 });
  await d.zoomTo(dialog(), { max: 1.4 });
  d.hold(0.9);
  d.zoomOut();
  await d.press('Escape', { animate: 180, after: 0.05 });

  await d.click(nav('LeetCode'), { after: 0.1 });
  d.caption('Post the daily LeetCode problem');
  d.hold(0.9);

  // Knowledge: upload, a source submodule, test search, search settings.
  await d.click(nav('Knowledge'), { after: 0.1 });
  d.caption('Upload documents for your agents');
  await d.click(page.getByRole('button', { name: 'Upload', exact: true }), { animate: 180, after: 0.05 });
  const drop = dialog().getByRole('button', { name: /Drop files here/ });
  await d.zoomTo(dialog(), { max: 1.4 });
  await d.glide({ x: 1210, y: 820 }, { real: false, speed: 1.5 });
  d.drag('build-season-handbook.pdf');
  d.hold(0.1);
  await d.glide(drop, { hover: false });
  await drop.evaluate((el) => {
    el.dispatchEvent(new DragEvent('dragover', { bubbles: true, cancelable: true, dataTransfer: new DataTransfer() }));
  });
  await d.shot(0.1);
  d.hold(0.2);
  d.endDrag();
  await drop.evaluate((el) => {
    const dt = new DataTransfer();
    dt.items.add(new File([new Uint8Array(2_412_000)], 'build-season-handbook.pdf', { type: 'application/pdf' }));
    el.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt }));
  });
  await d.shot(0.12);
  d.hold(0.25);
  await d.click(dialog().getByRole('button', { name: 'Upload', exact: true }), { after: 0.7 });
  await d.click(dialog().getByRole('button', { name: 'Done' }), { animate: 180, after: 0.05 });

  d.caption('Add public pages in one step');
  await d.zoomTo(card('Source submodules'), { max: 1.5 });
  await d.click(card('Source submodules').getByRole('button', { name: 'Add' }), { after: 0.8 });

  d.caption('Test what your agents will find');
  d.zoomOut(0.7);
  const search = card('Test search');
  await d.scroll(await d.scrollTarget(search, 40), { dur: 0.8 });
  await d.zoomTo(search, { max: 1.5 });
  await d.click(page.getByLabel('Search query'), { after: 0.05 });
  await d.type('When is the next build night?', { cps: 30 });
  await d.click(page.getByRole('button', { name: 'Search', exact: true }), { after: 0.1 });
  await d.scroll(await d.scrollTarget(search, 40), { dur: 0.5 });
  await d.zoomTo(search, { max: 1.45 });
  d.hold(1.0);

  d.caption('Tune how search ranks passages');
  d.zoomOut(0.7);
  await d.scroll(0, { dur: 0.6 });
  await d.click(page.getByRole('button', { name: 'Search settings' }), { animate: 180, after: 0.05 });
  await d.zoomTo(dialog(), { max: 1.3 });
  d.hold(0.9);
  d.zoomOut();
  await d.press('Escape', { animate: 180, after: 0.05 });

  // Compute and tokens: Godfather, hosting and tokens.
  await d.click(nav('Godfather'), { after: 0.1 });
  d.caption('Schedule GPU pods for workshops');
  await d.click(page.getByRole('button', { name: 'Sessions of Workshop GPU (A40)' }), { animate: 180, after: 0.05 });
  await d.zoomTo(dialog(), { max: 1.45 });
  await d.click(dialog().getByPlaceholder('Intro to PyTorch'), { after: 0.05 });
  await d.type('Robot arm workshop', { cps: 30 });
  await d.click(dialog().getByRole('button', { name: 'Add session' }), { after: 0.7 });
  d.zoomOut();
  await d.press('Escape', { animate: 180, after: 0.05 });

  await d.click(nav('Apps'), { after: 0.1 });
  d.caption("Deploy your org's apps");
  await d.click(page.getByRole('button', { name: 'rover-telemetry' }).or(page.getByText('rover-telemetry', { exact: true })).first(), { animate: 180, after: 0.05 });
  await d.zoomTo(dialog(), { max: 1.3, dy: -120 });
  await d.click(dialog().getByRole('button', { name: 'Deploy', exact: true }), { after: 0.05 });
  await d.click(dialog().getByPlaceholder('v1.2.0'), { after: 0.05, hover: false });
  await d.type('v1.9.0', { cps: 20 });
  await d.click(dialog().getByRole('button', { name: 'Preview' }), { after: 0.45 });
  await d.click(dialog().getByRole('button', { name: 'Deploy v1.9.0' }), { after: 0.7 });
  d.zoomOut();
  await d.press('Escape', { animate: 180, after: 0.05 });

  await d.click(nav('Tokens'), { after: 0.1 });
  d.caption('Give an agent a scoped token');
  await d.click(page.getByRole('button', { name: 'New token' }), { after: 0.05 });
  await d.zoomTo(card('New token'), { max: 1.45 });
  await d.click(page.getByPlaceholder('club-agent'), { after: 0.05 });
  await d.type('events-agent', { cps: 26 });
  await d.click(page.getByLabel('knowledge:read'), { after: 0.05 });
  await d.click(page.getByLabel('calendar:read'), { after: 0.1 });
  await d.click(page.getByRole('button', { name: 'Create token' }), { after: 0.1 });
  await d.zoomTo(card('Token created'), { max: 1.6 });
  d.hold(0.9);
  d.zoomOut();

  // Activity, then the rail and the overview.
  await d.click(nav('Activity'), { after: 0.1 });
  d.caption('Every change goes in the audit log');
  await d.zoomTo(page.locator('main').first(), { max: 1.3, dy: -160 });
  d.hold(0.8);
  await d.click(page.getByRole('tab', { name: 'Knowledge runs' }), { animate: 180, after: 0.6 });
  d.zoomOut();
  await d.glide({ x: 760, y: 420 }, { real: false });

  d.caption('Collapse the sidebar', ['Ctrl', 'B']);
  d.hold(0.3);
  await d.press('Control+b', { animate: 220, after: 0.2 });
  await d.click(nav('Overview'), { after: 0.2 });
  d.hold(0.9);
  d.endCaption();
}

// ---------------------------------------------------------------------------------------------------------------
// The renderer: a page that draws one video frame from a frame state.

function compositorHtml() {
  const font = pathToFileURL(join(root, 'node_modules/@fontsource-variable/geist/files/geist-latin-wght-normal.woff2')).href;
  const orgs = ['ais', 'soda'].map((n) => pathToFileURL(join(root, `public/orgs/${n}.svg`)).href);
  const logo =
    '<svg viewBox="0 0 24 24" fill="none"><rect x="3" y="15" width="18" height="5" rx="1.5" fill="currentColor"/>' +
    '<rect x="3" y="9" width="18" height="4" rx="1.5" fill="currentColor" opacity="0.55"/>' +
    '<rect x="3" y="4" width="18" height="3" rx="1.5" fill="currentColor" opacity="0.25"/></svg>';
  return `<!doctype html>
<html><head><meta charset="utf-8"><style>
@font-face { font-family: Geist; src: url("${font}") format("woff2"); font-weight: 100 900; }
* { box-sizing: border-box; margin: 0; }
html, body { width: ${OUT.width}px; height: ${OUT.height}px; overflow: hidden; background: #f4f5f8; }
body { font-family: Geist, system-ui, sans-serif; -webkit-font-smoothing: antialiased; }
#stage { position: relative; width: ${OUT.width}px; height: ${OUT.height}px; overflow: hidden;
  background:
    radial-gradient(900px 620px at 12% 8%, rgba(147, 197, 253, 0.55), transparent 70%),
    radial-gradient(820px 640px at 92% 96%, rgba(196, 181, 253, 0.45), transparent 70%),
    radial-gradient(700px 500px at 70% 20%, rgba(253, 230, 138, 0.22), transparent 70%),
    linear-gradient(160deg, #f8fafc 0%, #eef1f7 100%); }
#scene { position: absolute; left: 0; top: 0; width: ${OUT.width}px; height: ${OUT.height}px; transform-origin: 0 0; will-change: transform; }
#win { position: absolute; left: ${WIN.x}px; top: ${WIN.y}px; width: ${WIN.width}px; height: ${WIN.height}px;
  border-radius: 14px; overflow: hidden; background: #f5f5f5;
  box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.09), 0 2px 6px rgba(15, 23, 42, 0.05), 0 28px 70px -18px rgba(15, 23, 42, 0.32); }
#bar { position: relative; height: ${BAR}px; display: flex; align-items: center; padding: 0 14px; gap: 8px;
  background: #fbfbfc; border-bottom: 1px solid rgba(15, 23, 42, 0.08); }
#bar i { width: 12px; height: 12px; border-radius: 50%; display: block; box-shadow: inset 0 0 0 0.5px rgba(0, 0, 0, 0.12); }
#title { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); max-width: 60%;
  display: flex; align-items: center; gap: 7px; height: 22px; padding: 0 12px; border-radius: 6px;
  background: rgba(15, 23, 42, 0.045); color: #52525b; font-size: 12.5px; white-space: nowrap; overflow: hidden; }
#title svg { width: 13px; height: 13px; color: #18181b; flex: none; }
#content { position: relative; width: ${WIN.width}px; height: ${VIEW.height * K}px; }
#content img { position: absolute; inset: 0; width: 100%; height: 100%; display: block; }
#cursor { position: absolute; left: 0; top: 0; width: 34px; height: 34px; transform-origin: 7.5px 4.4px;
  filter: drop-shadow(0 2px 3px rgba(0, 0, 0, 0.28)); }
.ripple { position: absolute; border-radius: 50%; border: 2px solid rgba(37, 99, 235, 0.75); background: rgba(37, 99, 235, 0.16); }
#chip { position: absolute; display: flex; align-items: center; gap: 10px; padding: 9px 14px 9px 10px; border-radius: 10px;
  background: #fff; color: #18181b; font-size: 14px; font-weight: 500; transform-origin: 0 0;
  box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.08), 0 12px 28px -8px rgba(15, 23, 42, 0.35); }
#chip b { display: grid; place-items: center; width: 26px; height: 30px; border-radius: 4px; background: #ef4444; color: #fff;
  font-size: 8.5px; font-weight: 700; letter-spacing: 0.02em; }
#caption { position: absolute; left: 50%; top: ${CAPTION_Y}px; display: flex; align-items: center; gap: 10px;
  padding: 11px 22px; border-radius: 999px; white-space: nowrap;
  background: rgba(17, 17, 20, 0.88); color: #fff; font-size: 23px; font-weight: 500; letter-spacing: -0.01em;
  box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.45); }
#caption kbd { font: inherit; font-size: 17px; font-weight: 600; min-width: 32px; padding: 3px 9px; border-radius: 7px; text-align: center;
  background: rgba(255, 255, 255, 0.14); box-shadow: inset 0 -2px 0 rgba(255, 255, 255, 0.12); }
#end { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center;
  background: rgba(246, 247, 250, 0.74); backdrop-filter: blur(16px); color: #0a0a0a; }
#end .mark { display: flex; align-items: center; gap: 22px; font-size: 92px; font-weight: 600; letter-spacing: -0.035em; }
#end .mark svg { width: 92px; height: 92px; }
#end p { margin-top: 18px; font-size: 32px; color: #52525b; letter-spacing: -0.01em; }
#end .orgs { margin-top: 44px; display: flex; align-items: center; gap: 16px; font-size: 20px; color: #52525b; }
#end .orgs span { display: flex; }
#end .orgs img { width: 46px; height: 46px; border-radius: 50%; padding: 7px; box-shadow: 0 0 0 3px #f6f7fa, 0 0 0 4px rgba(0, 0, 0, 0.08); }
#end .orgs img + img { margin-left: -14px; }
</style></head><body>
<div id="stage">
  <div id="scene">
    <div id="win">
      <div id="bar"><i style="background:#ff5f57"></i><i style="background:#febc2e"></i><i style="background:#28c840"></i>
        <div id="title">${logo}<span id="title-text">Platform</span></div></div>
      <div id="content"><img id="a" alt=""><img id="b" alt=""></div>
    </div>
    <div id="ripples"></div>
    <div id="chip"><b>PDF</b><span id="chip-text"></span></div>
    <svg id="cursor" viewBox="0 0 34 34"><path d="M7.5 4.4 L7.5 25.8 L12.9 20.9 L16.4 28.9 L20 27.4 L16.6 19.6 L23.8 19.6 Z"
      fill="#111" stroke="#fff" stroke-width="1.9" stroke-linejoin="round"/></svg>
  </div>
  <div id="caption"></div>
  <div id="end">
    <div class="mark">${logo}<span>Platform</span></div>
    <p>Infrastructure for student organizations</p>
    <div class="orgs"><span><img src="${orgs[0]}" style="background:#0a0a0a" alt=""><img src="${orgs[1]}" style="background:#fff" alt=""></span>
      Built by AI Society and SoDA at ASU</div>
  </div>
</div>
<script>
const cache = new Map();
function image(src) {
  let entry = cache.get(src);
  if (!entry) {
    const img = new Image();
    img.src = src;
    entry = { img, ready: img.decode().catch(() => {}) };
    cache.set(src, entry);
    if (cache.size > 24) cache.delete(cache.keys().next().value);
  }
  return entry;
}
const $ = (id) => document.getElementById(id);
let captionKey = null;
window.apply = async (s) => {
  for (const src of s.prefetch) image(src);
  const a = $('a'), b = $('b');
  if (s.prev) { const e = image(s.prev); await e.ready; if (a.src !== e.img.src) a.src = e.img.src; await a.decode().catch(() => {}); }
  const e = image(s.cur); await e.ready;
  if (b.src !== e.img.src) b.src = e.img.src;
  await b.decode().catch(() => {});
  a.style.opacity = s.prev ? 1 : 0;
  b.style.opacity = s.alpha;
  $('title-text').textContent = s.title;
  const c = s.cam;
  const intro = s.intro;
  $('scene').style.transform =
    'translate(' + ${OUT.width / 2} + 'px,' + (${OUT.height / 2} + (1 - intro) * 26) + 'px) scale(' + c.z * (0.97 + 0.03 * intro) + ') translate(' + -c.fx + 'px,' + -c.fy + 'px)';
  $('scene').style.opacity = intro;
  const cur = $('cursor');
  cur.style.transform = 'translate(' + (s.pointer.x - 7.5 * s.pointer.size) + 'px,' + (s.pointer.y - 4.4 * s.pointer.size) + 'px) scale(' + s.pointer.size * s.pointer.press + ')';
  cur.style.transformOrigin = '0 0';
  cur.style.opacity = s.pointer.opacity;
  $('ripples').innerHTML = s.ripples
    .map((r) => '<div class="ripple" style="left:' + (r.x - r.r) + 'px;top:' + (r.y - r.r) + 'px;width:' + 2 * r.r + 'px;height:' + 2 * r.r + 'px;opacity:' + r.o + '"></div>')
    .join('');
  const chip = $('chip');
  chip.style.opacity = s.chip ? s.chip.o : 0;
  if (s.chip) {
    $('chip-text').textContent = s.chip.label;
    chip.style.transform = 'translate(' + s.chip.x + 'px,' + s.chip.y + 'px) rotate(-3deg) scale(' + (0.9 + 0.1 * s.chip.o) + ')';
  }
  const cap = $('caption');
  if (s.caption) {
    const key = s.caption.text + (s.caption.keys || []).join('+');
    if (key !== captionKey) {
      captionKey = key;
      cap.innerHTML = '';
      const span = document.createElement('span');
      span.textContent = s.caption.text;
      cap.append(span);
      for (const k of s.caption.keys || []) {
        const kbd = document.createElement('kbd');
        kbd.textContent = k;
        cap.append(kbd);
      }
    }
    cap.style.opacity = s.caption.o;
    cap.style.transform = 'translate(-50%, ' + (-50 + (1 - s.caption.o) * 22) + '%) scale(' + (0.96 + 0.04 * s.caption.o) + ')';
  } else cap.style.opacity = 0;
  const end = $('end');
  end.style.opacity = s.end;
  end.style.visibility = s.end > 0 ? 'visible' : 'hidden';
  end.style.backdropFilter = 'blur(' + 16 * s.end + 'px)';
  for (const [i, el] of [...end.children].entries()) {
    const p = Math.min(1, Math.max(0, s.end * 1.6 - i * 0.22));
    el.style.opacity = p;
    el.style.transform = 'translateY(' + (1 - p) * 18 + 'px)';
  }
};
</script></body></html>`;
}

// The state of one frame at time t, from the timeline.
function frameState(d: Director, t: number, endAt: number, cursorScale: number) {
  let i = 0;
  while (i + 1 < d.shots.length && d.shots[i + 1].t <= t) i++;
  const cur = d.shots[i];
  const alpha = cur.fade ? clamp01((t - cur.t) / cur.fade) : 1;
  const prev = alpha < 1 && i > 0 ? d.shots[i - 1] : null;

  let p = d.pointer;
  const firstMove = d.moves[0];
  p = firstMove ? firstMove.a : p;
  for (const m of d.moves) {
    if (t < m.t0) break;
    if (t >= m.t1) {
      p = m.b;
      continue;
    }
    const e = easeInOut((t - m.t0) / (m.t1 - m.t0));
    const u = 1 - e;
    p = { x: u * u * m.a.x + 2 * u * e * m.c.x + e * e * m.b.x, y: u * u * m.a.y + 2 * u * e * m.c.y + e * e * m.b.y };
  }
  const sp = toScene(p);

  let press = 1;
  const ripples = [];
  for (const c of d.clicks) {
    const dt = t - c.t;
    if (dt < -0.01 || dt > 0.6) continue;
    press = Math.min(press, 1 - 0.16 * (dt < 0.07 ? dt / 0.07 : clamp01(1 - (dt - 0.07) / 0.2)));
    const q = clamp01(dt / 0.55);
    const s = toScene(c);
    ripples.push({ x: s.x, y: s.y, r: 6 + 26 * (1 - (1 - q) ** 3), o: 1 - q });
  }

  let chip = null;
  for (const g of d.drags) {
    const t1 = g.t1 ?? Infinity;
    if (t < g.t0 || t > t1 + 0.2) continue;
    const o = Math.min(clamp01((t - g.t0) / 0.2), clamp01((t1 + 0.2 - t) / 0.2));
    chip = { x: sp.x + 16, y: sp.y + 22, o, label: g.label };
  }

  let caption = null;
  if (t < endAt) {
    for (const c of d.captions) {
      const t1 = c.t1 ?? endAt;
      if (t < c.t0 || t >= t1) continue;
      caption = { text: c.text, keys: c.keys, o: Math.min(clamp01((t - c.t0) / 0.28), clamp01((t1 - t) / 0.2)) };
    }
  }

  const end = clamp01((t - endAt) / 0.8);
  const next = d.shots.slice(i + 1, i + 4).map((s) => pathToFileURL(s.file).href);
  return {
    cur: pathToFileURL(cur.file).href,
    prev: prev ? pathToFileURL(prev.file).href : null,
    alpha,
    prefetch: next,
    title: cur.title,
    cam: d.camAt(t),
    intro: easeCamera(clamp01(t / 0.7)),
    pointer: { ...sp, size: cursorScale, press, opacity: 1 - end },
    ripples,
    chip,
    caption,
    end,
  };
}

type FrameState = ReturnType<typeof frameState>;

async function render(browser: Browser, d: Director, endAt: number, duration: number) {
  const html = join(work, 'compositor.html');
  writeFileSync(html, compositorHtml());
  const context = await browser.newContext({ viewport: OUT, deviceScaleFactor: 1 });
  const page = await context.newPage();
  await page.goto(pathToFileURL(html).href);
  await page.evaluate(() => document.fonts.ready);

  const master = join(work, 'master.mkv');
  const ffmpeg = spawn(
    'ffmpeg',
    ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'png', '-i', '-', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '4', '-pix_fmt', 'yuv444p', master],
    { stdio: ['pipe', 'inherit', 'inherit'] },
  );
  const done = new Promise<void>((ok, fail) => ffmpeg.on('close', (code) => (code === 0 ? ok() : fail(new Error(`ffmpeg exited with ${code}`)))));
  const frames = Math.round(duration * FPS);
  const started = Date.now();
  for (let f = 0; f < frames; f++) {
    const shown = f / FPS;
    const t = shown * WARP < endAt ? shown * WARP : endAt + (shown - endAt / WARP);
    await page.evaluate((s) => window.apply(s), frameState(d, t, endAt, 1.0));
    const png = await page.screenshot({ type: 'png' });
    if (!ffmpeg.stdin.write(png)) await new Promise((ok) => ffmpeg.stdin.once('drain', ok));
    if (f % (FPS * 5) === 0) console.log(`frame ${f}/${frames} (${Math.round((Date.now() - started) / 1000)} s)`);
  }
  ffmpeg.stdin.end();
  await done;
  await context.close();
  return master;
}

function run(args: string) {
  execSync(`ffmpeg -y -loglevel error ${args}`, { stdio: 'inherit' });
}

function encode(master: string, posterAt: number) {
  mkdirSync(out, { recursive: true });
  const mp4 = join(out, 'platform-demo.mp4');
  const webm = join(out, 'platform-demo.webm');
  const poster = join(out, 'poster.webp');
  const crf = process.env.DEMO_CRF ?? '23';
  run(`-i "${master}" -an -c:v libx264 -preset veryslow -tune animation -crf ${crf} -pix_fmt yuv420p -g ${FPS * 4} -movflags +faststart "${mp4}"`);
  const vp9 = process.env.DEMO_VP9_CRF ?? '36';
  const log = join(work, 'vp9');
  const common = `-an -c:v libvpx-vp9 -b:v 0 -crf ${vp9} -pix_fmt yuv420p -row-mt 1 -tile-columns 2 -g ${FPS * 4} -passlogfile "${log}"`;
  run(`-i "${master}" ${common} -pass 1 -deadline good -cpu-used 4 -f null /dev/null`);
  run(`-i "${master}" ${common} -pass 2 -deadline good -cpu-used 1 "${webm}"`);
  run(`-ss ${posterAt.toFixed(3)} -i "${master}" -frames:v 1 -c:v libwebp -quality 90 "${poster}"`);
  for (const file of [mp4, webm, poster]) console.log(`${file} ${Math.round(statSync(file).size / 1024)} KB`);
}

async function main() {
  rmSync(join(work, 'shots'), { recursive: true, force: true });
  mkdirSync(work, { recursive: true });
  const server = await preview({ root, preview: { port: PORT, strictPort: true }, logLevel: 'warn' });
  const browser = await chromium.launch({ executablePath: process.env.PLAYWRIGHT_CHROMIUM || undefined });
  try {
    const context = await browser.newContext({ viewport: VIEW, deviceScaleFactor: SCALE, colorScheme: 'light', reducedMotion: 'reduce' });
    await context.addInitScript(() => {
      if (!sessionStorage.getItem('demo.started')) {
        sessionStorage.setItem('demo.started', '1');
        localStorage.clear();
        localStorage.setItem('platform.theme', 'light');
      }
    });
    await context.route('**/api/**', demoApi());
    const page = await context.newPage();
    const d = new Director(page);
    const started = Date.now();
    await story(d);
    const endAt = d.t;
    const duration = endAt / WARP + 2.8;
    console.log(`recorded ${d.shots.length} screenshots in ${Math.round((Date.now() - started) / 1000)} s; video ${duration.toFixed(1)} s`);
    writeFileSync(join(work, 'timeline.json'), JSON.stringify({ shots: d.shots.length, captions: d.captions, endAt, duration }, null, 2));
    await context.close();
    if (process.env.DEMO_ONLY === 'record') return;
    const master = await render(browser, d, endAt, duration);
    encode(master, 0.9);
    if (process.env.DEMO_COPY) copyFileSync(join(out, 'platform-demo.mp4'), process.env.DEMO_COPY);
  } finally {
    await browser.close();
    await new Promise((ok) => server.httpServer.close(ok));
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

