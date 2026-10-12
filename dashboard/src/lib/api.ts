import { tokens } from './auth';
import { runtimeSetting } from './runtime-config';

export const API_URL =
  (runtimeSetting('VITE_API_URL') ?? (import.meta.env.VITE_API_URL as string | undefined))?.replace(/\/$/, '') ??
  'http://localhost:8000';

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

// One refresh at a time: requests that fail together wait for the same new access token.
let refreshing: Promise<boolean> | null = null;

function refresh(): Promise<boolean> {
  refreshing ??= refreshOnce().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

async function refreshOnce(): Promise<boolean> {
  const refreshToken = tokens.refresh();
  if (!refreshToken) return false;
  const response = await fetch(`${API_URL}/api/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) return false;
  const body = (await response.json()) as { access_token: string };
  tokens.set(body.access_token);
  return true;
}

const UNREACHABLE =
  'Could not reach the API. It may be restarting or have stopped mid-request. Check the server logs, then try again.';

// The JSON body of a response, or null when it is empty or not JSON, such as a proxy error page.
function parse(text: string): { error?: string; message?: string } | null {
  try {
    return text ? JSON.parse(text) : null;
  } catch {
    return null;
  }
}

// Officer routes answer an expired access token with 403 and this message, other routes with 401.
const EXPIRED_MESSAGE = 'Token is expired!';

async function expiredAccess(response: Response): Promise<boolean> {
  if (response.status === 401) return true;
  if (response.status !== 403 || !tokens.refresh()) return false;
  return parse(await response.clone().text())?.message === EXPIRED_MESSAGE;
}

// Sends a request with the access token, refreshing it once when the API says the token is expired.
async function request(path: string, init: RequestInit, retried = false): Promise<Response> {
  const headers = new Headers(init.headers);
  const access = tokens.access();
  if (access) headers.set('Authorization', `Bearer ${access}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    // fetch rejects only when no response arrived: the API is down, restarting, or the connection dropped.
    throw new ApiError(UNREACHABLE, 0);
  }
  if (!retried && (await expiredAccess(response)) && (await refresh())) return request(path, init, true);
  return response;
}

function failure(response: Response, body: { error?: string; message?: string } | null): ApiError {
  if (response.status === 401) tokens.clear();
  const fallback =
    response.status >= 502 && response.status <= 524
      ? `The API did not answer (${response.status}). It may be restarting or the request took too long.`
      : `Request failed (${response.status})`;
  return new ApiError(body?.error ?? body?.message ?? fallback, response.status);
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await request(path, init);
  const body = parse(await response.text());
  if (!response.ok) throw failure(response, body);
  return body as T;
}

// A binary response, such as a file attachment, as a Blob.
export async function apiBlob(path: string, init: RequestInit = {}): Promise<Blob> {
  const response = await request(path, init);
  if (!response.ok) {
    throw failure(response, parse(await response.text()));
  }
  return response.blob();
}

export const send = <T>(path: string, method: string, body?: unknown) =>
  api<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });

export function loginUrl(): string {
  return `${API_URL}/api/auth/login?client=dashboard`;
}

export async function exchangeLoginCode(code: string): Promise<void> {
  const body = await send<{ access_token: string; refresh_token: string }>('/api/auth/exchange', 'POST', { code });
  tokens.set(body.access_token, body.refresh_token);
}
