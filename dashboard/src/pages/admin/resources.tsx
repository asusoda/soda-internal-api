import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Gauge, SlidersHorizontal } from 'lucide-react';
import { useState } from 'react';
import { UseBar } from '../../components/limits';
import { Badge, Button, Card, CardHeader, Dialog, EmptyState, ErrorNote, FormActions, Input, Mono, Select, SkeletonRows, Table, Td, Th, Tr } from '../../components/ui';
import { api, send } from '../../lib/api';
import { byUse, limitText } from '../../lib/limits';
import type { AllLimits, LimitChange, LimitRow, OrgLimits } from '../../lib/types';

const KEY = ['superadmin-limits'];

// Each org, the limits it is near, and its most used limits. Edit opens the org's limits.
export function ResourcesCard() {
  const [open, setOpen] = useState<OrgLimits | null>(null);
  const all = useQuery({ queryKey: KEY, queryFn: () => api<AllLimits>('/api/superadmin/limits') });
  const orgs = all.data?.orgs ?? [];
  return (
    <Card>
      <CardHeader
        title="Resources"
        hint="What each org uses of its limits. A limit that an org uses 80% of or more is marked. LIMIT_<KEY> in .env sets the default for all orgs."
      />
      {all.error ? (
        <div className="p-4">
          <ErrorNote error={all.error} />
        </div>
      ) : null}
      {all.isLoading ? <SkeletonRows rows={3} /> : null}
      {all.data && !orgs.length ? (
        <EmptyState icon={Gauge} title="No organizations">
          Add an org to see its use.
        </EmptyState>
      ) : null}
      {orgs.length ? (
        <Table>
          <thead>
            <tr>
              <Th>Organization</Th>
              <Th className="hidden w-1/3 md:table-cell">Most used</Th>
              <Th>
                <span className="sr-only">Actions</span>
              </Th>
            </tr>
          </thead>
          <tbody>
            {orgs.map((o) => {
              const top = byUse(o.limits.filter((row) => row.enabled && row.value !== null)).slice(0, 2);
              return (
                <Tr key={o.org.id}>
                  <Td className="w-full max-w-0">
                    <div className="truncate font-medium">{o.org.name}</div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Mono className="truncate">{o.org.prefix}</Mono>
                      {o.near.length ? <Badge tone="warn">Near {o.near.length} {o.near.length === 1 ? 'limit' : 'limits'}</Badge> : null}
                      {o.overrides.length ? <Badge tone="active">{o.overrides.length} set for this org</Badge> : null}
                    </div>
                  </Td>
                  <Td className="hidden md:table-cell">
                    <div className="space-y-2">
                      {top.map((row) => (
                        <div key={row.key}>
                          <div className="truncate text-xs">{row.label}</div>
                          <UseBar row={row} />
                        </div>
                      ))}
                    </div>
                  </Td>
                  <Td>
                    <div className="flex justify-end">
                      <Button onClick={() => setOpen(o)} aria-label={`Limits of ${o.org.name}`}>
                        <SlidersHorizontal className="size-4" />
                        <span className="hidden sm:inline">Limits</span>
                      </Button>
                    </div>
                  </Td>
                </Tr>
              );
            })}
          </tbody>
        </Table>
      ) : null}
      <Dialog open={open !== null} onClose={() => setOpen(null)} title="Limits" description={open?.org.name} wide>
        {open ? <LimitsForm key={open.org.id} org={open} onClose={() => setOpen(null)} /> : null}
      </Dialog>
    </Card>
  );
}

type Mode = 'default' | 'number' | 'none';
type Draft = Record<string, { mode: Mode; text: string }>;

function initial(row: LimitRow): { mode: Mode; text: string } {
  if (!row.override) return { mode: 'default', text: row.default === null ? '' : String(row.default) };
  return row.value === null ? { mode: 'none', text: '' } : { mode: 'number', text: String(row.value) };
}

const isCount = (text: string) => /^\d{1,13}$/.test(text);

// The changes to send: only the limits whose draft differs from the saved value.
function changes(rows: LimitRow[], draft: Draft): Record<string, LimitChange> {
  const out: Record<string, LimitChange> = {};
  for (const row of rows) {
    const was = initial(row);
    const now = draft[row.key];
    if (now.mode === was.mode && (now.mode !== 'number' || now.text === was.text)) continue;
    out[row.key] = now.mode === 'default' ? 'default' : now.mode === 'none' ? null : Number(now.text);
  }
  return out;
}

function LimitsForm({ org, onClose }: { org: OrgLimits; onClose: () => void }) {
  const client = useQueryClient();
  const rows = [...org.limits].sort((a, b) => Number(b.enabled) - Number(a.enabled) || a.module.localeCompare(b.module) || a.label.localeCompare(b.label));
  const [draft, setDraft] = useState<Draft>(() => Object.fromEntries(rows.map((row) => [row.key, initial(row)])));
  const pending = changes(rows, draft);
  const count = Object.keys(pending).length;
  const valid = rows.every((row) => draft[row.key].mode !== 'number' || isCount(draft[row.key].text));
  const save = useMutation({
    mutationFn: () => send<OrgLimits>(`/api/superadmin/limits/${org.org.id}`, 'PUT', { limits: pending }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: KEY });
      onClose();
    },
  });
  const set = (key: string, next: Partial<{ mode: Mode; text: string }>) => setDraft((d) => ({ ...d, [key]: { ...d[key], ...next } }));
  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <div className="max-h-[60vh] space-y-4 overflow-y-auto pr-1">
        {rows.map((row) => {
          const d = draft[row.key];
          return (
            <div key={row.key} className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,16rem)] sm:items-start">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm font-medium">{row.label}</span>
                  {row.enabled ? null : <Badge>Module off</Badge>}
                </div>
                <Mono className="truncate">{row.key}</Mono>
                <UseBar row={row} className="mt-1.5" />
              </div>
              <div className="flex gap-2">
                <Select value={d.mode} onChange={(e) => set(row.key, { mode: e.target.value as Mode })} aria-label={`How to set ${row.label}`}>
                  <option value="default">Default ({limitText(row.default, '', row.window)})</option>
                  <option value="number">Number</option>
                  <option value="none">No limit</option>
                </Select>
                {d.mode === 'number' ? (
                  <Input
                    inputMode="numeric"
                    value={d.text}
                    onChange={(e) => set(row.key, { text: e.target.value.trim() })}
                    aria-invalid={!isCount(d.text)}
                    aria-label={`${row.label}, ${row.unit || 'value'}`}
                    className="w-28"
                  />
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
      <FormActions error={save.error ?? undefined}>
        <Button variant="primary" disabled={!valid || !count || save.isPending}>
          {count ? `Save ${count} ${count === 1 ? 'change' : 'changes'}` : 'Save'}
        </Button>
        <Button type="button" variant="ghost" onClick={onClose}>
          Cancel
        </Button>
      </FormActions>
    </form>
  );
}
