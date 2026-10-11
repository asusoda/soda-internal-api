import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { Select } from '../../components/ui';
import { api } from '../../lib/api';
import type { HostingProvider } from '../../lib/types';

// The provider of rows from before the provider choice, and of requests that name none.
export const DEFAULT_PROVIDER = 'runpod';

export function useProviders(prefix: string) {
  return useQuery({
    queryKey: ['hosting', prefix, 'providers'],
    queryFn: () => api<{ providers: HostingProvider[] }>(`/api/dashboard/${prefix}/hosting/providers`).then((body) => body.providers),
    enabled: Boolean(prefix),
    staleTime: 60_000,
  });
}

// The first configured provider, else the default.
export function firstConfigured(providers: HostingProvider[] | undefined): string {
  return providers?.find((p) => p.configured)?.name ?? DEFAULT_PROVIDER;
}

// The display name of a provider. RunPod is known before the list loads.
export function providerTitle(providers: HostingProvider[] | undefined, name: string | null | undefined): string {
  const key = name || DEFAULT_PROVIDER;
  return providers?.find((p) => p.name === key)?.title ?? (key === 'runpod' ? 'RunPod' : key);
}

// A select of the registered providers. A provider the org has not connected is disabled, with a link to Integrations.
export function ProviderField({
  prefix,
  providers,
  value,
  onChange,
  hint,
}: {
  prefix: string;
  providers: HostingProvider[] | undefined;
  value: string;
  onChange: (name: string) => void;
  hint: string;
}) {
  const list = providers ?? [];
  const missing = list.filter((p) => !p.configured);
  return (
    <label className="block space-y-1.5">
      <span className="block text-sm font-medium">Provider</span>
      <Select value={value} onChange={(e) => onChange(e.target.value)} disabled={!providers}>
        {list.length ? null : <option value={value}>{providerTitle(providers, value)}</option>}
        {list.map((p) => (
          <option key={p.name} value={p.name} disabled={!p.configured}>
            {p.configured ? p.title : `${p.title} (not connected)`}
          </option>
        ))}
      </Select>
      <span className="block text-xs text-pretty text-muted">
        {hint}
        {missing.length ? (
          <>
            {' '}
            Connect {missing.map((p) => p.title).join(', ')} on{' '}
            <Link to={`/${prefix}/explore?tab=integrations`} className="underline hover:text-fg">
              Integrations
            </Link>
            .
          </>
        ) : null}
      </span>
    </label>
  );
}
