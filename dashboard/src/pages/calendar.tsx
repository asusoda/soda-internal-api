import { IntegrationHint } from '../components/integration-hint';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CalendarDays, CalendarPlus, Info, RefreshCw } from 'lucide-react';
import { useState } from 'react';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  cx,
  EmptyState,
  ErrorNote,
  Field,
  FormActions,
  Input,
  OkNote,
  PageHeader,
  SkeletonRows,
  Switch,
  Table,
  Td,
  Th,
  Tr,
} from '../components/ui';
import { api, send } from '../lib/api';
import { timeAgo, when } from '../lib/format';
import { useCurrentOrg } from '../lib/org';
import type { CalendarEvent, CalendarSettings } from '../lib/types';

function CalendarForm({ orgId, saved }: { orgId: number; saved: CalendarSettings }) {
  const client = useQueryClient();
  const initial = {
    notion: saved.notion_database_id ?? '',
    google: saved.google_calendar_id ?? '',
    sync: saved.calendar_sync_enabled,
  };
  const [draft, setDraft] = useState(initial);
  const changed = draft.notion !== initial.notion || draft.google !== initial.google || draft.sync !== initial.sync;
  const save = useMutation({
    mutationFn: () =>
      send(`/api/organizations/${orgId}/calendar`, 'PUT', {
        notion_database_id: draft.notion || null,
        google_calendar_id: draft.google || null,
        calendar_sync_enabled: draft.sync,
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['calendar-settings', orgId] }),
  });
  return (
    <form
      className="space-y-5 p-4"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Notion database ID" hint="The events database the sync reads.">
          <Input
            value={draft.notion}
            onChange={(e) => setDraft({ ...draft, notion: e.target.value.trim() })}
            placeholder="1a2b3c4d5e6f..."
            className="font-mono"
            spellCheck={false}
          />
        </Field>
        <Field label="Google calendar ID" hint="The calendar the sync writes to.">
          <Input
            value={draft.google}
            onChange={(e) => setDraft({ ...draft, google: e.target.value.trim() })}
            placeholder="abc123@group.calendar.google.com"
            className="font-mono"
            spellCheck={false}
          />
        </Field>
      </div>
      <div className="flex items-center gap-3 rounded-lg border border-line p-3">
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium">Sync Notion to Google Calendar</div>
          <div className="mt-0.5 text-xs text-muted">Runs on the server's calendar sync schedule.</div>
        </div>
        <Switch checked={draft.sync} onChange={(sync) => setDraft({ ...draft, sync })} label="Sync Notion to Google Calendar" />
      </div>
      <p className="flex items-start gap-2 rounded-lg border border-line bg-panel-2/40 p-3 text-xs text-pretty text-muted">
        <Info className="mt-px size-3.5 shrink-0" aria-hidden />
        Sync is off by default. Read the Calendar sync docs before you turn it on.
      </p>
      <FormActions error={save.error}>
        <Button variant="primary" disabled={!changed || save.isPending}>
          Save calendar
        </Button>
        {save.isSuccess && !changed ? <span className="text-xs text-muted">Saved</span> : null}
      </FormActions>
    </form>
  );
}

const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

// An event start as a short local date, with the time when the event has one.
function eventWhen(start: string): string {
  if (DATE_ONLY.test(start)) {
    const [y, m, d] = start.split('-').map(Number);
    return new Date(y, m - 1, d).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
  }
  return when(start);
}

// Whether an event ends now or later. A date with no time counts until the end of that day.
function upcoming(event: CalendarEvent, now: number): boolean {
  const last = event.end ?? event.start;
  const time = DATE_ONLY.test(last) ? new Date(`${last}T23:59:59`).getTime() : new Date(last).getTime();
  return Number.isNaN(time) || time >= now;
}

function Events({ prefix, database }: { prefix: string; database: string | null }) {
  const configured = Boolean(database);
  const events = useQuery({
    queryKey: ['calendar-events', prefix, database],
    queryFn: () => api<{ events: CalendarEvent[]; total_events: number }>(`/api/calendar/${prefix}/events`),
    enabled: configured,
    retry: false,
  });
  const now = Date.now();
  const list = (events.data?.events ?? []).filter((e) => upcoming(e, now)).sort((a, b) => a.start.localeCompare(b.start));
  return (
    <Card>
      <CardHeader title="Upcoming events" />
      {!configured ? (
        <EmptyState icon={CalendarDays} title="No Notion database">
          Set the Notion database ID to see events.
        </EmptyState>
      ) : events.error ? (
        <div className="p-4">
          <ErrorNote error={events.error} />
        </div>
      ) : events.isLoading ? (
        <SkeletonRows rows={4} />
      ) : list.length ? (
        <Table>
          <thead>
            <tr>
              <Th>Event</Th>
              <Th className="text-right sm:text-left">Starts</Th>
              <Th className="hidden md:table-cell">Location</Th>
            </tr>
          </thead>
          <tbody>
            {list.map((e) => (
              <Tr key={e.id}>
                <Td className="w-full max-w-0">
                  <div className="truncate font-medium">{e.title}</div>
                  {e.location ? <div className="truncate text-xs text-muted md:hidden">{e.location}</div> : null}
                </Td>
                <Td className="text-right text-xs whitespace-nowrap text-muted tabular-nums sm:text-left">{eventWhen(e.start)}</Td>
                <Td className="hidden max-w-56 truncate text-muted md:table-cell">{e.location ?? ''}</Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      ) : (
        <EmptyState icon={CalendarDays} title="No upcoming events">
          Add events to the Notion database. They show here on the next load.
        </EmptyState>
      )}
    </Card>
  );
}

function SettingsCard({ orgId, prefix, saved }: { orgId: number; prefix: string; saved: CalendarSettings }) {
  const client = useQueryClient();
  const setup = useMutation({
    mutationFn: () => send<{ calendar_id: string }>(`/api/calendar/${prefix}/setup`, 'POST', {}),
    onSuccess: () => client.invalidateQueries({ queryKey: ['calendar-settings', orgId] }),
  });
  const last = saved.last_sync_at;
  return (
    <Card>
      <CardHeader
        title="Settings"
        action={<Badge tone={last ? 'ok' : 'muted'}>{last ? `Synced ${timeAgo(last)}` : 'Never synced'}</Badge>}
      />
      {!saved.google_calendar_id ? (
        <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
          <p className="min-w-0 flex-1 text-sm text-muted">
            No Google calendar is set. The server can make one with the org's Google service account.
          </p>
          <Button onClick={() => setup.mutate()} disabled={setup.isPending}>
            <CalendarPlus className="size-4" /> Create calendar
          </Button>
          {setup.error ? <ErrorNote error={setup.error} /> : null}
        </div>
      ) : null}
      <CalendarForm key={`${orgId}-${saved.google_calendar_id}`} orgId={orgId} saved={saved} />
    </Card>
  );
}

export function CalendarPage() {
  const { org, prefix } = useCurrentOrg();
  const client = useQueryClient();
  const settings = useQuery({
    queryKey: ['calendar-settings', org?.id],
    queryFn: () => api<CalendarSettings>(`/api/organizations/${org?.id}/calendar`),
    enabled: org !== undefined,
  });
  const sync = useMutation({
    mutationFn: () => send<{ message?: string }>(`/api/calendar/${prefix}/sync`, 'POST', {}),
    onSettled: () => {
      client.invalidateQueries({ queryKey: ['calendar-settings', org?.id] });
      client.invalidateQueries({ queryKey: ['calendar-events', prefix] });
    },
  });
  const configured = Boolean(settings.data?.notion_database_id);
  return (
    <>
      <PageHeader
        title="Calendar"
        description="Notion events copied to Google Calendar."
        action={
          <Button variant="primary" onClick={() => sync.mutate()} disabled={!configured || sync.isPending}>
            <RefreshCw className={cx('size-4', sync.isPending && 'animate-spin')} />
            {sync.isPending ? 'Syncing' : 'Sync now'}
          </Button>
        }
      />
      <IntegrationHint keys={['notion', 'google']} />
      {sync.error ? (
        <div className="mb-4">
          <ErrorNote error={sync.error} />
        </div>
      ) : sync.data ? (
        <OkNote className="mb-4">{sync.data.message ?? 'Sync done.'}</OkNote>
      ) : null}
      <div className="space-y-6">
        {settings.data && org ? (
          <SettingsCard orgId={org.id} prefix={prefix} saved={settings.data} />
        ) : settings.error ? (
          <ErrorNote error={settings.error} />
        ) : (
          <Card>
            <SkeletonRows rows={3} />
          </Card>
        )}
        {settings.data ? <Events prefix={prefix} database={settings.data.notion_database_id} /> : null}
      </div>
    </>
  );
}
