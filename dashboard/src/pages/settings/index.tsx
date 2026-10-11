import { useQuery } from '@tanstack/react-query';
import { type ReactNode, useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router';
import { Card, CardHeader, cx, ErrorNote, PageHeader, PageSkeleton, SkeletonRows } from '../../components/ui';
import { api } from '../../lib/api';
import { useCurrentOrg } from '../../lib/org';
import { useBranding, useIntegrations, useOrganization } from '../../lib/queries';
import { LimitTable } from '../../components/limits';
import { byUse, PAID_BY } from '../../lib/limits';
import type { LimitRow, Organization, SecretState } from '../../lib/types';
import { BrandingForm } from './branding';
import { GeneralForm } from './general';
import { SecretRow } from './secrets';

type Section = { id: string; label: string };

// Sections that moved to their own pages, for links made before the move.
const MOVED: Record<string, string> = {
  '#calendar': 'calendar',
  '#leetcode': 'leetcode',
  '#modules': 'explore',
  '#modules-link': 'explore',
};

// The id of the section nearest the top of the viewport.
function useActiveSection(ids: string[]): string | undefined {
  const [active, setActive] = useState<string>();
  const key = ids.join(',');
  useEffect(() => {
    const seen = new Map<string, boolean>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) seen.set(entry.target.id, entry.isIntersecting);
        const first = key.split(',').find((id) => seen.get(id));
        if (first) setActive(first);
      },
      { rootMargin: '-80px 0px -55% 0px' },
    );
    for (const id of key.split(',')) {
      const node = document.getElementById(id);
      if (node) observer.observe(node);
    }
    return () => observer.disconnect();
  }, [key]);
  return active;
}

function SectionNav({ sections }: { sections: Section[] }) {
  const active = useActiveSection(sections.map((s) => s.id)) ?? sections[0]?.id;
  return (
    <nav aria-label="Settings sections" className="min-w-0 lg:sticky lg:top-10 lg:self-start">
      <ul className="-mx-4 flex gap-1 overflow-x-auto px-4 pb-1 sm:mx-0 sm:px-0 lg:flex-col lg:gap-0.5 lg:overflow-visible">
        {sections.map((s) => (
          <li key={s.id} className="shrink-0">
            <a
              href={`#${s.id}`}
              aria-current={active === s.id ? 'location' : undefined}
              className={cx(
                'flex h-8 items-center rounded-md px-2.5 text-sm whitespace-nowrap transition-colors',
                active === s.id ? 'bg-panel-2 font-medium text-fg' : 'text-muted hover:bg-panel-2/60 hover:text-fg',
              )}
            >
              {s.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function SettingsSection({ id, children }: { id: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-20 md:scroll-mt-8">
      {children}
    </section>
  );
}

function Pending({ error, loading }: { error: unknown; loading: boolean }) {
  if (error) {
    return (
      <div className="p-4">
        <ErrorNote error={error} />
      </div>
    );
  }
  return loading ? <SkeletonRows rows={3} /> : null;
}

function GeneralSection({ org }: { org: Organization }) {
  const detail = useOrganization(org.id);
  return (
    <Card>
      <CardHeader title="General" />
      {detail.data ? <GeneralForm key={org.id} org={detail.data} /> : <Pending error={detail.error} loading={detail.isLoading} />}
    </Card>
  );
}

function BrandingSection({ org, prefix }: { org: Organization; prefix: string }) {
  const branding = useBranding(prefix);
  return (
    <Card>
      <CardHeader title="Branding" />
      {branding.data ? (
        <BrandingForm key={JSON.stringify(branding.data)} prefix={prefix} name={org.name} saved={branding.data} />
      ) : (
        <Pending error={branding.error} loading={branding.isLoading} />
      )}
    </Card>
  );
}

function SecretsSection({ orgId, prefix }: { orgId: number; prefix: string }) {
  const integrations = useIntegrations(prefix);
  const owned = new Set((integrations.data?.integrations ?? []).flatMap((i) => i.fields.map((f) => f.name)));
  const secrets = useQuery({
    queryKey: ['secrets', orgId],
    queryFn: () => api<{ configured: boolean; secrets: SecretState[] }>(`/api/organizations/${orgId}/secrets`),
  });
  return (
    <Card>
      <CardHeader
        title="Secrets"
        hint={
          <>
            Webhook URLs and app values. Service keys are on{' '}
            <Link to={`/${prefix}/explore?tab=integrations`} className="underline underline-offset-2 hover:text-fg">
              Integrations
            </Link>
            .
          </>
        }
      />
      {secrets.data && !secrets.data.configured ? (
        <div className="p-4">
          <ErrorNote error="SECRETS_KEY is not set on the server, so secrets cannot be saved." />
        </div>
      ) : null}
      <Pending error={secrets.error} loading={secrets.isLoading} />
      {secrets.data?.secrets
        .filter((s) => !owned.has(s.name))
        .map((s) => (
          <SecretRow key={s.name} orgId={orgId} secret={s} />
        ))}
    </Card>
  );
}

function LimitsSection({ orgId }: { orgId: number }) {
  const limits = useQuery({
    queryKey: ['limits', orgId],
    queryFn: () => api<{ limits: LimitRow[] }>(`/api/organizations/${orgId}/limits`),
  });
  return (
    <Card>
      <CardHeader
        title="Limits"
        hint="What this org may use of the shared server, for the modules that are on. Only the Platform superadmin changes them."
      />
      <Pending error={limits.error} loading={limits.isLoading} />
      {(['org', 'metered'] as const).map((paid) => {
        const rows = (limits.data?.limits ?? []).filter((r) => r.paid_by === paid);
        if (!rows.length) return null;
        return (
          <div key={paid}>
            <div className="border-t border-line px-4 pt-3 pb-2">
              <h3 className="text-xs font-semibold tracking-wide text-muted uppercase">{PAID_BY[paid].title}</h3>
              <p className="text-xs text-muted">{PAID_BY[paid].text}</p>
            </div>
            <LimitTable rows={byUse(rows)} />
          </div>
        );
      })}
      {limits.data ? (
        <p className="border-t border-line px-4 py-3 text-xs text-muted">
          {PAID_BY.shared.title}: {PAID_BY.shared.text} The pages of the submodules you subscribe to are shared.
        </p>
      ) : null}
    </Card>
  );
}

// Scrolls to the section in the URL hash once the page shows, or opens the page a section moved to.
function useHashSection(prefix: string, ready: boolean) {
  const { hash } = useLocation();
  const navigate = useNavigate();
  useEffect(() => {
    if (MOVED[hash]) {
      navigate(`/${prefix}/${MOVED[hash]}`, { replace: true });
      return;
    }
    if (ready && hash) document.getElementById(hash.slice(1))?.scrollIntoView();
  }, [hash, prefix, ready, navigate]);
}

export function SettingsPage() {
  const { org, prefix } = useCurrentOrg();
  useHashSection(prefix, Boolean(org));
  if (!org) return <PageSkeleton />;
  const sections: (Section & { body: ReactNode })[] = [
    { id: 'general', label: 'General', body: <GeneralSection org={org} /> },
    { id: 'branding', label: 'Branding', body: <BrandingSection org={org} prefix={prefix} /> },
    { id: 'secrets', label: 'Secrets', body: <SecretsSection orgId={org.id} prefix={prefix} /> },
    { id: 'limits', label: 'Limits', body: <LimitsSection orgId={org.id} /> },
  ];
  return (
    <>
      <PageHeader title="Settings" />
      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[160px_minmax(0,1fr)] lg:gap-10">
        <SectionNav sections={sections} />
        <div className="min-w-0 space-y-6">
          {sections.map((s) => (
            <SettingsSection key={s.id} id={s.id}>
              {s.body}
            </SettingsSection>
          ))}
        </div>
      </div>
    </>
  );
}
