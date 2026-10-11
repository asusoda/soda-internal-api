import { CheckCheck, RotateCcw, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { moduleLabel, NotificationItem } from '../../components/notifications';
import { SelectionBar, useSelection } from '../../components/selection';
import { Button, Card, EmptyState, ErrorNote, Select, ShowMore, SkeletonRows, useShowMore } from '../../components/ui';
import { useCurrentOrg } from '../../lib/org';
import { type NotificationAction, useNotificationChange, useNotifications } from '../../lib/queries';

// Problems that need an officer and events of the org, with resolve, reopen and delete for the selected rows.
// A problem cannot be deleted: it goes away when its cause is fixed.
export function NotificationsTab() {
  const { prefix } = useCurrentOrg();
  const { data, isLoading, error } = useNotifications(prefix);
  const change = useNotificationChange(prefix);
  const [status, setStatus] = useState<'open' | 'resolved'>('open');
  const [module, setModule] = useState('');
  const all = data?.notifications ?? [];
  const modules = useMemo(() => [...new Set(all.map((n) => n.module))], [all]);
  const shown = useMemo(
    () => all.filter((n) => Boolean(n.resolved_at) === (status === 'resolved') && (!module || n.module === module)),
    [all, status, module],
  );
  const page = useShowMore(shown, `${status}:${module}`, 50);
  const pick = useSelection(page.shown.map((n) => n.id));
  const events = new Set(all.filter((n) => n.kind === 'event').map((n) => n.id));
  const deletable = pick.ids.filter((id) => events.has(id));
  const run = (action: NotificationAction, ids: string[]) => change.mutate({ action, ids }, { onSuccess: pick.clear });

  const filters = (
    <>
      {modules.length > 1 ? (
        <Select value={module} onChange={(e) => setModule(e.target.value)} aria-label="Feature" className="h-8 w-40! text-xs">
          <option value="">All features</option>
          {modules.map((m) => (
            <option key={m} value={m}>
              {moduleLabel(m)}
            </option>
          ))}
        </Select>
      ) : null}
      <Select value={status} onChange={(e) => setStatus(e.target.value as 'open' | 'resolved')} aria-label="Status" className="h-8 w-32! text-xs">
        <option value="open">Open {data ? `(${data.open})` : ''}</option>
        <option value="resolved">Resolved</option>
      </Select>
    </>
  );

  return (
    <div className="grid gap-4">
      {error ? <ErrorNote error={error} /> : null}
      {change.error ? <ErrorNote error={change.error} /> : null}
      <Card data-selecting={pick.count > 0}>
        <SelectionBar
          count={pick.count}
          total={shown.length}
          all={pick.all}
          some={pick.some}
          onToggleAll={pick.toggleAll}
          onClear={pick.clear}
          noun="notifications"
          extra={filters}
        >
          {status === 'open' ? (
            <Button variant="ghost" disabled={change.isPending} onClick={() => run('resolve', pick.ids)}>
              <CheckCheck className="size-4" /> Resolve
            </Button>
          ) : (
            <Button variant="ghost" disabled={change.isPending} onClick={() => run('reopen', pick.ids)}>
              <RotateCcw className="size-4" /> Reopen
            </Button>
          )}
          <Button
            variant="ghost"
            className="hover:text-bad"
            disabled={change.isPending || !deletable.length}
            title={deletable.length ? undefined : 'Only events can be deleted. Resolve a problem instead.'}
            onClick={() => {
              if (confirm(`Delete ${deletable.length} ${deletable.length === 1 ? 'event' : 'events'}? This cannot be undone.`)) {
                run('delete', deletable);
              }
            }}
          >
            <Trash2 className="size-4" /> Delete{deletable.length && deletable.length !== pick.count ? ` ${deletable.length}` : ''}
          </Button>
        </SelectionBar>
        {isLoading ? (
          <SkeletonRows rows={6} />
        ) : page.shown.length ? (
          <>
            <ul className="divide-y divide-line">
              {page.shown.map((n) => (
                <NotificationItem key={n.id} n={n} selected={pick.has(n.id)} onSelect={() => pick.toggle(n.id)} />
              ))}
            </ul>
            <ShowMore list={page} noun="notifications" />
          </>
        ) : (
          <EmptyState icon={CheckCheck} title={status === 'open' ? 'Nothing needs attention' : 'Nothing resolved'}>
            {status === 'open' ? 'New problems and events show here and on the bell.' : 'Resolved notifications show here.'}
          </EmptyState>
        )}
      </Card>
    </div>
  );
}
