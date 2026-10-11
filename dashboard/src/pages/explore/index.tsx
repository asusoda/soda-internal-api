import { useMutation, useQueryClient } from '@tanstack/react-query';
import { type ReactNode, useDeferredValue, useState } from 'react';
import { TabBar, useTabParam } from '../../components/tabs';
import { Button, Dialog, ErrorNote, FormActions, Notice, PageHeader, PageSkeleton, SearchInput, Spinner } from '../../components/ui';
import { send } from '../../lib/api';
import { useCurrentOrg } from '../../lib/org';
import { useModuleCatalog } from '../../lib/queries';
import type { CatalogModule } from '../../lib/types';
import { IntegrationsTab } from './integrations';
import { ModuleCard, ModuleGrid } from './modules';
import { SubmodulesTab } from './submodules';

const TABS = [
  { id: 'features', label: 'Features' },
  { id: 'shared', label: 'Shared' },
  { id: 'integrations', label: 'Integrations' },
] as const;

// The tab ids before the rename, from old links and notifications
const ALIASES = { modules: 'features', submodules: 'shared' } as const;

function ModulesTab({ query }: { query: string }) {
  const { org, prefix } = useCurrentOrg();
  const client = useQueryClient();
  const catalog = useModuleCatalog(prefix);
  const [removing, setRemoving] = useState<CatalogModule | null>(null);
  const [notice, setNotice] = useState<ReactNode>(null);
  const change = useMutation({
    mutationFn: ({ m, on }: { m: CatalogModule; on: boolean }) =>
      send(`/api/organizations/${org?.id}/modules`, 'PUT', { modules: { [m.name]: on } }),
    onSuccess: () => {
      setRemoving(null);
      client.invalidateQueries({ queryKey: ['catalog', prefix] });
      client.invalidateQueries({ queryKey: ['modules', org?.id] });
      client.invalidateQueries({ queryKey: ['overview'] });
    },
  });

  if (catalog.isLoading || !org) return <PageSkeleton />;
  if (catalog.error || !catalog.data) return <ErrorNote error={catalog.error ?? 'No data'} />;

  return (
    <>
      {notice ? <Notice onDismiss={() => setNotice(null)}>{notice}</Notice> : null}
      {change.error ? (
        <div className="mb-4">
          <ErrorNote error={change.error} />
        </div>
      ) : null}
      <ModuleGrid
        categories={catalog.data.categories}
        modules={catalog.data.modules}
        query={query}
        render={(m) => (
          <ModuleCard
            key={m.name}
            m={m}
            prefix={prefix}
            busy={change.isPending}
            onAdd={() => change.mutate({ m, on: true })}
            onRemove={() => setRemoving(m)}
          />
        )}
      />
      <Dialog
        open={removing !== null}
        onClose={() => setRemoving(null)}
        title={`Remove ${removing?.title ?? ''}?`}
        description="Its data stays and comes back when you add it again."
      >
        <FormActions>
          <Button variant="danger" disabled={change.isPending} onClick={() => removing && change.mutate({ m: removing, on: false })}>
            {change.isPending ? <Spinner className="size-3.5" /> : null} Remove
          </Button>
          <Button variant="ghost" onClick={() => setRemoving(null)}>
            Cancel
          </Button>
        </FormActions>
      </Dialog>
    </>
  );
}

function SubmodulesTabFor({ query }: { query: string }) {
  const { prefix } = useCurrentOrg();
  return <SubmodulesTab prefix={prefix} query={query} />;
}

// Everything an org can add: features (modules), shared content (submodules) it subscribes to, and services it connects.
export function ExplorePage() {
  const [tab, setTab] = useTabParam(TABS, ALIASES);
  const [query, setQuery] = useState('');
  const deferred = useDeferredValue(query);
  return (
    <>
      <PageHeader title="Explore" description="Add features, subscribe to shared content and connect services." docs="concepts" />
      <TabBar
        label="Explore"
        tabs={TABS}
        value={tab}
        onChange={setTab}
        action={
          <SearchInput
            className="w-full sm:w-64"
            placeholder={tab === 'features' ? 'Search features' : tab === 'shared' ? 'Search shared content' : 'Search integrations'}
            aria-label="Search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        }
      />
      {tab === 'features' ? (
        <ModulesTab query={deferred} />
      ) : tab === 'shared' ? (
        <SubmodulesTabFor query={deferred} />
      ) : (
        <IntegrationsTab query={deferred} />
      )}
    </>
  );
}
