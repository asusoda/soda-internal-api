import { ChevronRight, ExternalLink } from 'lucide-react';
import { Badge, cx, Dot, Mono, Table, Td, Th, Tr } from '../../components/ui';
import { deployTone, timeAgo } from '../../lib/format';
import type { App, HostingProvider } from '../../lib/types';
import { providerTitle } from './providers';
import { actorLabel, DEFAULT_MANIFEST_PATH } from './shared';

export function AppTable({ apps, providers, onOpen }: { apps: App[]; providers?: HostingProvider[]; onOpen: (name: string) => void }) {
  return (
    <Table>
      <thead>
        <tr>
          <Th>App</Th>
          <Th className="hidden lg:table-cell">Provider</Th>
          <Th className="hidden sm:table-cell">Tag</Th>
          <Th>Status</Th>
          <Th className="hidden md:table-cell">Last deploy</Th>
          <Th>
            <span className="sr-only">Open</span>
          </Th>
        </tr>
      </thead>
      <tbody>
        {apps.map((app) => {
          const latest = app.latest_deployment;
          const tone = deployTone(latest?.status ?? null);
          return (
            <Tr key={app.name} className="cursor-pointer" onClick={() => onOpen(app.name)}>
              <Td className="w-full max-w-0">
                <div className="flex items-center gap-2.5">
                  <Dot tone={tone} />
                  <div className="min-w-0">
                    <button
                      type="button"
                      className="block max-w-full truncate rounded-sm text-left font-medium focus-visible:outline-2 focus-visible:outline-ring"
                      onClick={(e) => {
                        e.stopPropagation();
                        onOpen(app.name);
                      }}
                    >
                      {app.name}
                    </button>
                    {app.url ? (
                      <a
                        href={app.url}
                        target="_blank"
                        rel="noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="inline-flex max-w-full items-center gap-1 truncate text-xs text-muted hover:text-fg hover:underline"
                      >
                        {new URL(app.url).host}
                        <ExternalLink className="size-3 shrink-0" />
                      </a>
                    ) : null}
                    <div className={cx('truncate text-xs', latest?.error ? 'text-bad' : 'text-muted')}>
                      {latest?.status === 'failed' && latest.error
                        ? latest.error
                        : app.description
                          ? app.description
                          : app.repo
                          ? `${app.repo}${app.manifest_path && app.manifest_path !== DEFAULT_MANIFEST_PATH ? ` · ${app.manifest_path}` : ''}`
                          : 'inline manifest'}
                    </div>
                  </div>
                </div>
              </Td>
              <Td className="hidden lg:table-cell">
                <Badge>{providerTitle(providers, app.provider ?? app.host)}</Badge>
              </Td>
              <Td className="hidden max-w-40 sm:table-cell">
                <Mono className="block truncate text-fg">{app.current_tag ?? '-'}</Mono>
              </Td>
              <Td>
                <Badge tone={tone}>{latest?.status ?? 'not deployed'}</Badge>
              </Td>
              <Td className="hidden text-xs whitespace-nowrap text-muted tabular-nums md:table-cell">
                {latest ? (
                  <>
                    {timeAgo(latest.started_at)}
                    {latest.actor ? <span className="text-muted/70"> · {actorLabel(latest.actor)}</span> : null}
                  </>
                ) : (
                  'never'
                )}
              </Td>
              <Td className="w-8 pl-0 text-muted">
                <ChevronRight className="size-4" />
              </Td>
            </Tr>
          );
        })}
      </tbody>
    </Table>
  );
}
