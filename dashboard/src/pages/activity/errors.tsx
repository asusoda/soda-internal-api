import { Bug, CheckCheck, RotateCcw, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';
import { useConfirm } from '../../components/confirm';
import { ErrorList } from '../../components/error-list';
import { SelectionBar, useSelection } from '../../components/selection';
import { Button, Card, EmptyState, ErrorNote, Select, SkeletonRows } from '../../components/ui';
import { useCurrentOrg } from '../../lib/org';
import { type ErrorAction, type ErrorStatus, useErrorChange, useErrors } from '../../lib/queries';

// The org's errors from the Platform error log, with resolve, reopen and delete for the selected rows.
export function ErrorsTab() {
  const { prefix } = useCurrentOrg();
  const [status, setStatus] = useState<ErrorStatus>('open');
  const list = useErrors(prefix, status);
  const change = useErrorChange(prefix);
  const errors = list.data?.errors ?? [];
  const pick = useSelection(errors.map((e) => e.id));
  const run = (action: ErrorAction, ids: number[]) => change.mutate({ action, ids }, { onSuccess: pick.clear });
  const confirm = useConfirm();

  return (
    <div className="grid gap-4">
      {list.error ? <ErrorNote error={list.error} /> : null}
      {change.error ? <ErrorNote error={change.error} /> : null}
      <Card data-selecting={pick.count > 0}>
        <SelectionBar
          count={pick.count}
          total={errors.length}
          all={pick.all}
          some={pick.some}
          onToggleAll={pick.toggleAll}
          onClear={pick.clear}
          noun={status === 'open' ? 'open errors' : 'resolved errors'}
          extra={
            <Select value={status} onChange={(e) => setStatus(e.target.value as ErrorStatus)} aria-label="Status" className="h-8 w-32! text-xs">
              <option value="open">Open</option>
              <option value="resolved">Resolved</option>
            </Select>
          }
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
            disabled={change.isPending}
            onClick={() => {
              void confirm(
                `Delete ${pick.count} ${pick.count === 1 ? 'error' : 'errors'}? An error that happens again starts a new row.`,
                'Delete',
              ).then((yes) => {
                if (yes) run('delete', pick.ids);
              });
            }}
          >
            <Trash2 className="size-4" /> Delete
          </Button>
        </SelectionBar>
        {list.isLoading ? (
          <SkeletonRows rows={5} />
        ) : errors.length ? (
          <ErrorList
            errors={errors}
            onChange={(action, ids) => run(action, ids)}
            busy={change.isPending}
            isSelected={pick.has}
            onSelect={pick.toggle}
          />
        ) : (
          <EmptyState icon={Bug} title={status === 'open' ? 'No open errors' : 'Nothing resolved'}>
            {status === 'open' ? 'Errors of the API, bot, jobs, MCP server and dashboard show here.' : 'Resolved errors stay here for 90 days.'}
          </EmptyState>
        )}
      </Card>
      <p className="text-xs text-muted">
        {list.data?.webhook_set ? 'A webhook sends new errors to a channel.' : 'No webhook sends errors to a channel.'}{' '}
        <Link to={`/${prefix}/webhooks`} className="text-fg underline-offset-2 hover:underline">
          Set webhooks
        </Link>
      </p>
    </div>
  );
}
