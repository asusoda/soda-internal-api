import { useQuery } from '@tanstack/react-query';
import { Building2, CircleCheck, Server, ShieldCheck, Unplug, UserX } from 'lucide-react';
import { useState } from 'react';
import { Button, Card, CardHeader, Dialog, EmptyState, ErrorNote, PageHeader, PageSkeleton, SkeletonRows, Stat, StatGrid } from '../../components/ui';
import { api } from '../../lib/api';
import { useOrganizations } from '../../lib/org';
import { isBotDown, useSuperadmin } from '../../lib/queries';
import type { AvailableGuild, OrganizationDetail, SuperadminDashboard } from '../../lib/types';
import { AuditCard } from './audit';
import { AddDialog, OfficerRoleDialog, RemoveDialog } from './dialogs';
import { ErrorsCard } from './errors';
import { PublishersCard } from './publishers';
import { ResourcesCard } from './resources';
import { ServerCard } from './server';
import { ServicesCard } from './services';
import { GuildsCard, OrganizationsCard } from './tables';

type Open = { kind: 'role' | 'remove'; org: OrganizationDetail } | { kind: 'add'; guild: AvailableGuild } | null;

function Superadmin() {
  const [open, setOpen] = useState<Open>(null);
  const orgList = useOrganizations();
  const dashboard = useQuery({
    queryKey: ['superadmin-dashboard'],
    queryFn: () => api<SuperadminDashboard>('/api/superadmin/dashboard'),
    retry: (count, error) => !isBotDown(error) && count < 2,
  });
  const orgs = dashboard.data?.existing_orgs ?? [];
  const guilds = dashboard.data?.available_guilds ?? [];
  const prefixes = (dashboard.data ? orgs : (orgList.data ?? [])).map((o) => o.prefix).sort();
  const close = () => setOpen(null);
  return (
    <>
      <PageHeader title="Superadmin" description="Every org on this deployment, and the server." />

      {dashboard.error ? (
        <Card className="mb-6">
          {isBotDown(dashboard.error) ? (
            <EmptyState
              icon={Unplug}
              title="Discord bot not available"
              action={
                <Button onClick={() => dashboard.refetch()} disabled={dashboard.isFetching}>
                  Try again
                </Button>
              }
            >
              Organizations and servers come from the bot. Check that the bot process is running, then try again.
            </EmptyState>
          ) : (
            <div className="p-4">
              <ErrorNote error={dashboard.error} />
            </div>
          )}
        </Card>
      ) : null}

      {dashboard.data ? (
        <StatGrid className="mb-6">
          <Stat label="Organizations" value={orgs.length} icon={<Building2 className="size-4" />} />
          <Stat label="Active" value={orgs.filter((o) => o.is_active).length} icon={<CircleCheck className="size-4" />} />
          <Stat label="No officer role" value={orgs.filter((o) => !o.officer_role_id).length} icon={<UserX className="size-4" />} />
          <Stat label="Servers to add" value={guilds.length} icon={<Server className="size-4" />} />
        </StatGrid>
      ) : null}

      <div className="mb-6 space-y-6">
        <ServerCard />
        <ServicesCard orgs={dashboard.data ? orgs : (orgList.data ?? [])} />
      </div>

      {!dashboard.error ? (
        <div className="mb-6 space-y-6">
          <Card>
            <CardHeader title="Organizations" />
            {dashboard.isLoading ? (
              <SkeletonRows />
            ) : (
              <OrganizationsCard orgs={orgs} onRole={(org) => setOpen({ kind: 'role', org })} onRemove={(org) => setOpen({ kind: 'remove', org })} />
            )}
          </Card>
          <Card>
            <CardHeader title="Discord servers without an org" />
            {dashboard.isLoading ? <SkeletonRows rows={2} /> : <GuildsCard guilds={guilds} onAdd={(guild) => setOpen({ kind: 'add', guild })} />}
          </Card>
          <ResourcesCard />
          {dashboard.data ? <PublishersCard orgs={orgs} /> : null}
        </div>
      ) : null}

      <div className="mb-6">
        <ErrorsCard prefixes={prefixes} />
      </div>

      <AuditCard prefixes={prefixes} />

      <Dialog open={open?.kind === 'role'} onClose={close} title="Officer role" description={open?.kind === 'role' ? open.org.name : undefined}>
        {open?.kind === 'role' ? <OfficerRoleDialog key={open.org.id} org={open.org} onClose={close} /> : null}
      </Dialog>
      <Dialog open={open?.kind === 'remove'} onClose={close} title="Remove org" description={open?.kind === 'remove' ? open.org.name : undefined}>
        {open?.kind === 'remove' ? <RemoveDialog key={open.org.id} org={open.org} onClose={close} /> : null}
      </Dialog>
      <Dialog open={open?.kind === 'add'} onClose={close} title="Add org" description="Make an org for this Discord server.">
        {open?.kind === 'add' ? <AddDialog key={open.guild.id} guild={open.guild} onClose={close} /> : null}
      </Dialog>
    </>
  );
}

export function AdminPage() {
  const superadmin = useSuperadmin();
  if (superadmin.isLoading) return <PageSkeleton stats />;
  if (superadmin.error) return <ErrorNote error={superadmin.error} />;
  if (!superadmin.data) {
    return (
      <>
        <PageHeader title="Superadmin" />
        <Card>
          <EmptyState icon={ShieldCheck} title="Superadmin only">
            Only the Platform superadmin can manage organizations and see the audit log for all of them.
          </EmptyState>
        </Card>
      </>
    );
  }
  return <Superadmin />;
}
