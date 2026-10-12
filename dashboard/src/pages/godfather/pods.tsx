import { useMutation } from '@tanstack/react-query';
import { CalendarClock, FolderOpen, Play, RotateCw, ShieldCheck, Square, Trash2, Users } from 'lucide-react';
import { useState } from 'react';
import { useConfirm } from '../../components/confirm';
import {
  Badge,
  Button,
  Dialog,
  Dot,
  Field,
  FormActions,
  Input,
  Mono,
  Spinner,
  Switch,
  Table,
  Td,
  Th,
  Tr,
} from '../../components/ui';
import { send } from '../../lib/api';
import { timeAgo } from '../../lib/format';
import type { HostingProvider, Pod } from '../../lib/types';
import { providerTitle, useProviders } from '../hosting/providers';
import {
  costLabel,
  machineLabel,
  MenuItem,
  MenuSeparator,
  podPath,
  RowMenu,
  statusLabel,
  statusTone,
  usePodAction,
  useRefreshGodfather,
} from './shared';
import { UsersEditor } from './members';

export type PodDialog = { kind: 'access' | 'members' | 'sessions' | 'files' | 'terminate'; pod: Pod };

export function AccessBadge({ pod }: { pod: Pod }) {
  if (pod.is_public) return <Badge tone="ok">All members</Badge>;
  const n = pod.allowed_users.length;
  return <Badge>{n ? `${n} listed` : 'Officers only'}</Badge>;
}

export function StatusBadge({ status }: { status: string | null }) {
  const tone = statusTone(status);
  return (
    <Badge tone={tone}>
      <Dot tone={tone} />
      {statusLabel(status)}
    </Badge>
  );
}

function PodRow({ prefix, pod, open, providers }: { prefix: string; pod: Pod; open: (d: PodDialog) => void; providers?: HostingProvider[] }) {
  const action = usePodAction(prefix, pod.id);
  const confirm = useConfirm();
  const running = pod.status === 'RUNNING';
  const gone = pod.status === 'GONE';
  const machine = machineLabel(pod.machine);
  const cost = costLabel(pod.cost_per_hour);
  const power = () => {
    if (!running) return action.mutate('start');
    void confirm(`Stop ${pod.name}? Members are disconnected and files outside the volume are lost.`, 'Stop').then((yes) => {
      if (yes) action.mutate('stop');
    });
  };
  return (
    <Tr>
      <Td className="w-full max-w-0 py-3">
        <div className="truncate font-medium">{pod.name}</div>
        <Mono className="block truncate sm:hidden">{pod.id}</Mono>
        <div className="mt-0.5 hidden truncate text-xs text-muted sm:block">
          {pod.created_at ? `created ${timeAgo(pod.created_at)}` : null}
        </div>
        {action.error ? <div className="mt-1 truncate text-xs text-bad">{(action.error as Error).message}</div> : null}
      </Td>
      <Td className="hidden whitespace-nowrap sm:table-cell">
        <Mono>{pod.id}</Mono>
      </Td>
      <Td className="whitespace-nowrap">
        <StatusBadge status={pod.status} />
      </Td>
      <Td className="hidden whitespace-nowrap xl:table-cell">
        <Badge>{providerTitle(providers, pod.provider)}</Badge>
      </Td>
      <Td className="hidden max-w-48 truncate text-sm md:table-cell" title={machine ?? undefined}>
        {machine ?? <span className="text-muted">-</span>}
      </Td>
      <Td className="hidden text-right text-xs whitespace-nowrap text-muted tabular-nums lg:table-cell">{cost ?? '-'}</Td>
      <Td className="hidden whitespace-nowrap lg:table-cell">
        <AccessBadge pod={pod} />
      </Td>
      <Td className="py-2 pr-2 pl-0 sm:pl-4">
        <div className="flex items-center justify-end gap-1">
          <Button
            onClick={power}
            disabled={action.isPending || gone}
            aria-label={`${running ? 'Stop' : 'Start'} ${pod.name}`}
            className="w-8 px-0 sm:w-auto sm:px-3"
          >
            {action.isPending ? (
              <Spinner className="size-3.5" />
            ) : running ? (
              <Square className="size-4 sm:size-3.5" />
            ) : (
              <Play className="size-4 sm:size-3.5" />
            )}
            <span className="hidden sm:inline">{running ? 'Stop' : 'Start'}</span>
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="max-sm:hidden"
            title="Files"
            aria-label={`Files on ${pod.name}`}
            onClick={() => open({ kind: 'files', pod })}
          >
            <FolderOpen className="size-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="max-sm:hidden"
            title="Members"
            aria-label={`Members of ${pod.name}`}
            onClick={() => open({ kind: 'members', pod })}
          >
            <Users className="size-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="max-sm:hidden"
            title="Sessions"
            aria-label={`Sessions of ${pod.name}`}
            onClick={() => open({ kind: 'sessions', pod })}
          >
            <CalendarClock className="size-4" />
          </Button>
          <RowMenu label={`More actions for ${pod.name}`}>
            {(close) => {
              const pick = (fn: () => void) => () => {
                close();
                fn();
              };
              return (
                <>
                  <MenuItem icon={FolderOpen} className="sm:hidden" onClick={pick(() => open({ kind: 'files', pod }))}>
                    Files
                  </MenuItem>
                  <MenuItem icon={CalendarClock} className="sm:hidden" onClick={pick(() => open({ kind: 'sessions', pod }))}>
                    Sessions
                  </MenuItem>
                  <MenuItem icon={Users} className="sm:hidden" onClick={pick(() => open({ kind: 'members', pod }))}>
                    Members
                  </MenuItem>
                  <MenuItem icon={ShieldCheck} onClick={pick(() => open({ kind: 'access', pod }))}>
                    Access
                  </MenuItem>
                  <MenuItem
                    icon={RotateCw}
                    disabled={!running || action.isPending}
                    onClick={pick(() => {
                      void confirm(`Restart ${pod.name}? Members are disconnected.`, 'Restart').then((yes) => {
                        if (yes) action.mutate('restart');
                      });
                    })}
                  >
                    Restart
                  </MenuItem>
                  <MenuSeparator />
                  <MenuItem icon={Trash2} danger onClick={pick(() => open({ kind: 'terminate', pod }))}>
                    Terminate
                  </MenuItem>
                </>
              );
            }}
          </RowMenu>
        </div>
      </Td>
    </Tr>
  );
}

export function PodsTable({ prefix, pods, open }: { prefix: string; pods: Pod[]; open: (d: PodDialog) => void }) {
  const providers = useProviders(prefix);
  return (
    <Table>
      <thead>
        <tr>
          <Th>Name</Th>
          <Th className="hidden sm:table-cell">Pod ID</Th>
          <Th>Status</Th>
          <Th className="hidden xl:table-cell">Provider</Th>
          <Th className="hidden md:table-cell">Machine</Th>
          <Th className="hidden text-right lg:table-cell">Cost</Th>
          <Th className="hidden lg:table-cell">Access</Th>
          <Th>
            <span className="sr-only">Actions</span>
          </Th>
        </tr>
      </thead>
      <tbody>
        {pods.map((pod) => (
          <PodRow key={pod.id} prefix={prefix} pod={pod} open={open} providers={providers.data} />
        ))}
      </tbody>
    </Table>
  );
}

export function AccessDialog({ prefix, pod, onClose }: { prefix: string; pod: Pod; onClose: () => void }) {
  const [isPublic, setPublic] = useState(pod.is_public);
  const [users, setUsers] = useState(pod.allowed_users);
  const refresh = useRefreshGodfather(prefix);
  const save = useMutation({
    mutationFn: () => send(podPath(prefix, pod.id), 'PUT', { is_public: isPublic, allowed_users: users }),
    onSuccess: () => {
      refresh();
      onClose();
    },
  });
  return (
    <Dialog open onClose={onClose} title={`Access to ${pod.name}`} description="Officers can always connect.">
      <form
        className="space-y-5"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <div className="flex items-start justify-between gap-4 rounded-lg border border-line p-3">
          <div>
            <div className="text-sm font-medium">Open to all members</div>
            <div className="mt-0.5 text-xs text-muted">Every member of the Discord server can connect while it runs.</div>
          </div>
          <Switch checked={isPublic} onChange={setPublic} label="Open to all members" />
        </div>
        <UsersEditor prefix={prefix} users={users} onChange={setUsers} />
        <FormActions error={save.error}>
          <Button variant="primary" disabled={save.isPending}>
            Save access
          </Button>
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </FormActions>
      </form>
    </Dialog>
  );
}

export function TerminateDialog({ prefix, pod, onClose }: { prefix: string; pod: Pod; onClose: () => void }) {
  const [typed, setTyped] = useState('');
  const action = usePodAction(prefix, pod.id);
  const providers = useProviders(prefix);
  return (
    <Dialog open onClose={onClose} title={`Terminate ${pod.name}`}>
      <form
        className="space-y-5"
        onSubmit={(e) => {
          e.preventDefault();
          action.mutate('terminate', { onSuccess: onClose });
        }}
      >
        <div className="rounded-lg border border-bad/30 bg-bad/10 p-3 text-sm text-pretty">
          This deletes the pod on {providerTitle(providers.data, pod.provider)} with its volume and every file on it, and removes its sessions. It cannot be
          undone.
        </div>
        <Field label={`Type ${pod.name} to confirm`}>
          <Input value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" spellCheck={false} />
        </Field>
        <FormActions error={action.error}>
          <Button
            variant="danger"
            disabled={typed !== pod.name || action.isPending}
            className="border-bad! bg-bad! text-white! hover:opacity-85"
          >
            {action.isPending ? <Spinner className="size-3.5" /> : <Trash2 className="size-4" />}
            Terminate pod
          </Button>
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </FormActions>
      </form>
    </Dialog>
  );
}
