import { AlertTriangle, ArrowRight, BellRing, Boxes, Bot, CalendarClock, Coins, Cpu, Database, GitBranch, ShoppingBag, Users } from 'lucide-react';
import { Link } from 'react-router';
import { ActivityList } from '../components/activity-list';
import { moduleLabel } from '../components/notifications';
import {
  Card,
  CardHeader,
  Dot,
  EmptyState,
  ErrorNote,
  Mono,
  PageHeader,
  PageSkeleton,
  quietLink,
  Row,
  Stat,
  StatGrid,
} from '../components/ui';
import { compact, deployTone, runTone, timeAgo } from '../lib/format';
import { useCurrentOrg } from '../lib/org';
import { useCi, useNotifications, useOverview } from '../lib/queries';
import { TrendsCard } from './overview-trends';

export function OverviewPage() {
  const { prefix } = useCurrentOrg();
  const { data, isLoading, error } = useOverview(prefix);
  const ci = useCi(prefix);
  const notes = useNotifications(prefix);
  if (isLoading) return <PageSkeleton stats />;
  if (error || !data) return <ErrorNote error={error ?? 'No data'} />;
  const s = data.sections;
  const runs = (ci.data?.repos ?? []).flatMap((r) => r.runs.slice(0, 1).map((run) => ({ repo: r.repo, ...run })));
  // A module missing from the list is always on.
  const on = (name: string) => data.modules.find((m) => m.name === name)?.enabled ?? true;
  const open = (notes.data?.notifications ?? []).filter((n) => !n.resolved_at);

  return (
    <>
      <PageHeader
        title="Overview"
        description={`Updated ${timeAgo(data.generated_at)}.`}
      />

      {open.length ? (
        <Link
          to={`/${prefix}/activity`}
          className="mb-6 flex animate-in items-center gap-3 rounded-lg border border-bad/30 bg-bad/5 px-4 py-3 text-sm transition-colors hover:bg-bad/10"
        >
          <AlertTriangle className="size-4 shrink-0 text-bad" />
          <span className="min-w-0 flex-1">
            <span className="font-medium">
              {open.length} {open.length === 1 ? 'problem needs' : 'problems need'} attention
            </span>
            <span className="ml-2 hidden text-muted sm:inline">
              {[...new Set(open.map((n) => moduleLabel(n.module)))].join(', ')}
            </span>
          </span>
          <span className="flex items-center gap-1 text-xs text-muted">
            Activity <ArrowRight className="size-3.5" />
          </span>
        </Link>
      ) : null}

      <StatGrid>
        {[
          <Stat key="members" label="Members" value={compact(s.members.total)} icon={<Users className="size-4" />} />,
          on('points') ? (
            <Stat
              key="points"
              label="Points"
              value={compact(s.points.total)}
              sub={`${compact(s.points.last_30_days)} in the last 30 days`}
              icon={<Coins className="size-4" />}
            />
          ) : null,
          on('godfather') ? (
            <Stat
              key="pods"
              label="Pods"
              value={s.godfather.pods.length}
              sub={`${s.godfather.sessions.length} upcoming sessions`}
              icon={<Cpu className="size-4" />}
            />
          ) : null,
          on('agents') ? (
            <Stat
              key="agents"
              label="Agent conversations"
              value={compact(s.agents.active_7_days)}
              sub={`${s.agents.members_7_days} members this week`}
              icon={<Bot className="size-4" />}
            />
          ) : null,
          on('knowledge') ? (
            <Stat key="knowledge" label="Knowledge sources" value={compact(s.knowledge.sources)} icon={<Database className="size-4" />} />
          ) : null,
          on('storefront') ? (
            <Stat key="store" label="Open orders" value={s.storefront.pending_orders} icon={<ShoppingBag className="size-4" />} />
          ) : null,
        ]
          .filter(Boolean)
          .slice(0, 4)}
      </StatGrid>

      <TrendsCard prefix={prefix} />

      <div className="mt-6 grid gap-6 md:grid-cols-2 xl:grid-cols-[repeat(auto-fit,minmax(15rem,1fr))]">
        <Card>
          <CardHeader
            title="CI"
            action={
              <Link to="activity?tab=ci" className={quietLink}>
                All runs
              </Link>
            }
          />
          {runs.length ? (
            runs.map((run) => (
              <a
                key={run.repo}
                href={run.url ?? undefined}
                target="_blank"
                rel="noreferrer"
                className="block transition-colors hover:bg-panel-2/50"
              >
                <Row>
                  <Dot tone={runTone(run.status, run.conclusion)} />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm">{run.repo}</div>
                    <div className="truncate text-xs text-muted">
                      {run.workflow} · {run.branch}
                    </div>
                  </div>
                  <span className="shrink-0 text-xs text-muted tabular-nums">{timeAgo(run.started_at)}</span>
                </Row>
              </a>
            ))
          ) : (
            <EmptyState icon={GitBranch}>
              Add repositories in{' '}
              <Link to="activity?tab=ci" className="text-fg underline underline-offset-2">
                CI runs
              </Link>
              .
            </EmptyState>
          )}
        </Card>

        {on('runpod') ? (
        <Card>
          <CardHeader
            title="Services"
            action={
              <Link to="hosting" className={quietLink}>
                Details
              </Link>
            }
          />
          {s.apps.apps.length ? (
            s.apps.apps.map((app) => (
              <Row key={app.name}>
                <Dot tone={deployTone(app.status)} />
                <span className="flex-1 truncate text-sm">{app.name}</span>
                <Mono>{app.tag ?? 'not deployed'}</Mono>
              </Row>
            ))
          ) : (
            <EmptyState icon={Boxes}>No apps registered.</EmptyState>
          )}
        </Card>
        ) : null}

        {on('feeds') ? (
        <Card>
          <CardHeader title="Feeds" />
          {s.feeds.feeds.length ? (
            s.feeds.feeds.map((f) => (
              <Row key={f.key}>
                <Dot tone={!f.enabled ? 'muted' : f.last_error ? 'bad' : 'ok'} />
                <span className="flex-1 truncate text-sm">{f.key}</span>
                <span className="text-xs text-muted tabular-nums">{f.posted_7_days} this week</span>
              </Row>
            ))
          ) : (
            <EmptyState icon={BellRing}>No feeds.</EmptyState>
          )}
        </Card>
        ) : null}

        {on('godfather') ? (
        <Card>
          <CardHeader
            title="Upcoming sessions"
            action={
              <Link to="godfather" className={quietLink}>
                Godfather
              </Link>
            }
          />
          {s.godfather.sessions.length ? (
            s.godfather.sessions.slice(0, 5).map((session) => (
              <Row key={`${session.pod_id}-${session.start_at}`}>
                <span className="flex-1 truncate text-sm">{session.title ?? session.pod_id}</span>
                <span className="text-xs text-muted tabular-nums">{timeAgo(session.start_at)}</span>
              </Row>
            ))
          ) : (
            <EmptyState icon={CalendarClock}>No sessions scheduled.</EmptyState>
          )}
        </Card>
        ) : null}

      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader
            title="Recent changes"
            action={
              <Link to="activity" className={quietLink}>
                Audit log
              </Link>
            }
          />
          <ActivityList entries={data.activity.slice(0, 8)} empty="No changes recorded yet." />
        </Card>

        <Card>
          <CardHeader title="Jobs" />
          <ActivityList entries={data.jobs.slice(0, 8)} empty="No job runs recorded for this organization." />
        </Card>
      </div>

    </>
  );
}
