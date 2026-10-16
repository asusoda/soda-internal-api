import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Button, Code, ErrorNote, Field, FormActions, Input, Mono, Select } from '../../components/ui';
import { api, send } from '../../lib/api';
import { useCurrentOrg } from '../../lib/org';
import type { AvailableGuild, GuildRole, OrganizationDetail } from '../../lib/types';
import { explain, useRefreshOrgs } from './shared';

// The prefix the server gives a new organization, from prefix_for in modules/superadmin/service.py.
function prefixFor(name: string, guildId: string): string {
  const prefix = name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 20).replace(/_+$/, '');
  return prefix.length >= 2 ? prefix : `org_${guildId.slice(-6)}`;
}

export function OfficerRoleDialog({ org, onClose }: { org: OrganizationDetail; onClose: () => void }) {
  const refresh = useRefreshOrgs();
  const [role, setRole] = useState(org.officer_role_id ?? '');
  const roles = useQuery({
    queryKey: ['guild-roles', org.guild_id],
    queryFn: () => api<{ roles: GuildRole[] }>(`/api/superadmin/guild_roles/${org.guild_id}`),
    retry: false,
  });
  const save = useMutation({
    mutationFn: () => send(`/api/superadmin/update_officer_role/${org.id}`, 'PUT', { officer_role_id: role }),
    onSuccess: () => {
      refresh(org);
      onClose();
    },
  });
  const list = roles.data?.roles ?? [];
  const unknown = role && roles.data && !list.some((r) => r.id === role);
  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      {roles.error ? <ErrorNote error={explain(roles.error)} /> : null}
      <Field label="Officer role" hint="Members with this role can use the dashboard for this organization.">
        <Select value={role} onChange={(e) => setRole(e.target.value)} disabled={!roles.data}>
          <option value="">{roles.isLoading ? 'Loading roles...' : 'No officer role'}</option>
          {unknown ? <option value={role}>Unknown role {role}</option> : null}
          {list.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </Select>
      </Field>
      {role ? (
        <p className="text-xs text-muted">
          Role ID <Code>{role}</Code>
        </p>
      ) : (
        <p className="text-xs text-muted">With no officer role, no member can open this org in the dashboard.</p>
      )}
      <FormActions error={save.error ? explain(save.error) : undefined}>
        <Button variant="primary" disabled={!roles.data || role === (org.officer_role_id ?? '') || save.isPending}>
          Save role
        </Button>
        <Button type="button" variant="ghost" onClick={onClose}>
          Cancel
        </Button>
      </FormActions>
    </form>
  );
}

export function RemoveDialog({ org, onClose }: { org: OrganizationDetail; onClose: () => void }) {
  const refresh = useRefreshOrgs();
  const navigate = useNavigate();
  const { prefix } = useCurrentOrg();
  const [typed, setTyped] = useState('');
  const remove = useMutation({
    mutationFn: () => send(`/api/superadmin/remove_org/${org.id}`, 'DELETE'),
    onSuccess: () => {
      refresh(org);
      onClose();
      if (org.prefix === prefix) navigate('/');
    },
  });
  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        if (typed === org.prefix) remove.mutate();
      }}
    >
      <div className="rounded-lg border border-bad/30 bg-bad/10 p-3 text-sm text-pretty text-bad">
        This deletes <strong className="font-semibold">{org.name}</strong> and all of its data: members, points, orders and settings. You cannot undo it.
      </div>
      <Field label={`Type ${org.prefix} to confirm`}>
        <Input
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          autoComplete="off"
          spellCheck={false}
          className="font-mono"
          placeholder={org.prefix}
        />
      </Field>
      <FormActions error={remove.error}>
        <Button variant="danger" disabled={typed !== org.prefix || remove.isPending}>
          Remove organization
        </Button>
        <Button type="button" variant="ghost" onClick={onClose}>
          Cancel
        </Button>
      </FormActions>
    </form>
  );
}

export function AddDialog({ guild, onClose }: { guild: AvailableGuild; onClose: () => void }) {
  const refresh = useRefreshOrgs();
  const add = useMutation({
    mutationFn: () => send(`/api/superadmin/add_org/${guild.id}`, 'POST'),
    onSuccess: () => {
      refresh();
      onClose();
    },
  });
  return (
    <div className="space-y-5">
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-6 gap-y-2 text-sm">
        <dt className="text-muted">Server</dt>
        <dd className="truncate font-medium">{guild.name}</dd>
        <dt className="text-muted">Server ID</dt>
        <dd>
          <Mono>{guild.id}</Mono>
        </dd>
        <dt className="text-muted">Prefix</dt>
        <dd>
          <Code>{prefixFor(guild.name, guild.id)}</Code>
        </dd>
      </dl>
      <p className="text-xs text-pretty text-muted">
        The org starts with default settings and no officer role. Set the officer role next so officers can sign in.
      </p>
      <FormActions error={add.error ? explain(add.error) : undefined}>
        <Button variant="primary" onClick={() => add.mutate()} disabled={add.isPending}>
          Add organization
        </Button>
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
      </FormActions>
    </div>
  );
}
