import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, Copy, KeyRound, Plus } from 'lucide-react';
import { useState } from 'react';
import { IntegrationIcon } from '../components/integration-icons';
import { Tooltip } from '../components/tooltip';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Checkbox,
  Code,
  DeleteButton,
  Dialog,
  cx,
  EmptyState,
  ErrorNote,
  Field,
  FormActions,
  Input,
  Mono,
  PageHeader,
  Select,
  SkeletonRows,
  Table,
  Td,
  Th,
  Tr,
} from '../components/ui';
import { api, send } from '../lib/api';
import { timeAgo } from '../lib/format';
import { useCurrentOrg } from '../lib/org';
import type { MachineToken, TokenIntegration } from '../lib/types';

type TokenList = {
  tokens: MachineToken[];
  scopes: Record<string, string>;
  integrations: TokenIntegration[];
  // Platform scopes and the integrations each one calls for the agent
  uses?: Record<string, string[]>;
  // The public URL of the MCP server (null when it has none) and whether clients can connect with OAuth
  mcp?: { url: string | null; oauth: boolean };
};

// What each limit takes, with an example.
const LIMIT_HINTS: Record<string, { label: string; placeholder: string; hint: string }> = {
  repos: {
    label: 'Repos',
    placeholder: 'my-org/website, my-org/*',
    hint: 'Calls may act only on these repos. Leave empty for every repo the key can reach.',
  },
  tools: {
    label: 'Tools',
    placeholder: 'github.*issue*, github.get_file_contents',
    hint: 'Only tools whose names match. Leave empty for all tools the scopes give.',
  },
};

function list(text: string): string[] {
  return text
    .split(/[\s,]+/)
    .map((v) => v.trim())
    .filter(Boolean);
}

function titles(keys: string[], integrations: TokenIntegration[]): string {
  const names = keys.map((key) => integrations.find((i) => i.key === key)?.title ?? key);
  return names.length > 1 ? `${names.slice(0, -1).join(', ')} and ${names.at(-1)}` : (names[0] ?? '');
}

function ScopeBox({
  scope,
  description,
  on,
  onChange,
  uses = [],
  integrations = [],
  disabled = false,
  tools,
}: {
  scope: string;
  description: string;
  on: boolean;
  onChange: (on: boolean) => void;
  uses?: string[];
  integrations?: TokenIntegration[];
  disabled?: boolean;
  // The tools the scope gives, shown under the description
  tools?: string;
}) {
  return (
    <label
      className={cx(
        'flex items-start gap-3 px-3 py-2.5 text-sm transition-colors',
        disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer hover:bg-panel-2/50',
      )}
    >
      <Checkbox checked={on} onChange={() => !disabled && onChange(!on)} label={scope} className="mt-0.5" />
      <span className="min-w-0 flex-1">
        <span className="block font-mono text-xs">{scope}</span>
        <span className="mt-0.5 block text-xs text-muted">{description}</span>
        {tools ? <span className="mt-1 block font-mono text-[11px] leading-relaxed text-muted">{tools}</span> : null}
      </span>
      {uses.length ? (
        <Tooltip label={`Uses ${titles(uses, integrations)} with the org's keys`} side="top">
          <span className="flex shrink-0 items-center gap-1 text-muted" aria-label={`Uses ${titles(uses, integrations)}`}>
            {uses.map((key) => (
              <IntegrationIcon key={key} name={key} className="size-3.5" />
            ))}
          </span>
        </Tooltip>
      ) : null}
    </label>
  );
}

// The tools a scope of an integration gives, as one line.
function toolLine(integration: TokenIntegration, scope: string): string | undefined {
  const names = integration.tools?.[scope] ?? [];
  if (names.length) return names.map((name) => name.split('.').slice(1).join('.')).join(' · ');
  if (integration.remote) {
    return scope.endsWith(':read')
      ? `The read-only tools of ${integration.title}'s MCP server`
      : `The other tools of ${integration.title}'s MCP server`;
  }
  return undefined;
}

function NewToken({
  orgId,
  scopes,
  integrations,
  uses,
  onDone,
}: {
  orgId: number;
  scopes: Record<string, string>;
  integrations: TokenIntegration[];
  uses: Record<string, string[]>;
  onDone: () => void;
}) {
  const client = useQueryClient();
  const [name, setName] = useState('');
  const [kind, setKind] = useState('agent');
  const [chosen, setChosen] = useState<string[]>([]);
  const [limitText, setLimitText] = useState<Record<string, string>>({});
  const [value, setValue] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const create = useMutation({
    mutationFn: () => {
      const limits: Record<string, Record<string, string[]>> = {};
      for (const integration of integrations) {
        if (!integration.scopes.some((scope) => chosen.includes(scope))) continue;
        for (const limit of integration.limits) {
          const values = list(limitText[`${integration.key}.${limit}`] ?? '');
          if (values.length)
            limits[integration.key] = {
              ...limits[integration.key],
              [limit]: values,
            };
        }
      }
      return send<{ token: string }>(`/api/organizations/${orgId}/tokens`, 'POST', { name, kind, scopes: chosen, limits });
    },
    onSuccess: (body) => {
      setValue(body.token);
      client.invalidateQueries({ queryKey: ['tokens', orgId] });
    },
  });
  const owned = new Set(integrations.flatMap((i) => i.scopes));
  const toggle = (scope: string) => (on: boolean) => setChosen(on ? [...chosen, scope] : chosen.filter((s) => s !== scope));
  if (value) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-muted">Copy the token now. It is not shown again.</p>
          <div className="flex gap-2">
            <Input readOnly value={value} className="font-mono" aria-label="New token" />
            <Button
              size="icon"
              aria-label="Copy token"
              onClick={() => {
                navigator.clipboard.writeText(value);
                setCopied(true);
              }}
            >
              {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
            </Button>
          </div>
        <Button onClick={onDone}>Done</Button>
      </div>
    );
  }
  return (
      <form
        className="space-y-5"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Name">
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="club-agent" required />
          </Field>
          <Field label="Kind">
            <Select value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="agent">agent</option>
              <option value="app">app</option>
            </Select>
          </Field>
        </div>
        <fieldset>
          <legend className="mb-1.5 text-sm font-medium">Platform scopes</legend>
          <div className="divide-y divide-line rounded-lg border border-line">
            {Object.entries(scopes)
              .filter(([scope]) => !owned.has(scope))
              .map(([scope, description]) => (
                <ScopeBox
                  key={scope}
                  scope={scope}
                  description={description}
                  on={chosen.includes(scope)}
                  onChange={toggle(scope)}
                  uses={uses[scope]}
                  integrations={integrations}
                />
              ))}
          </div>
        </fieldset>
        <h3 className="text-sm font-medium">Integration tools</h3>
        {integrations.map((integration) => {
          const picked = integration.scopes.some((scope) => chosen.includes(scope));
          const usedBy = (integration.used_by ?? []).filter((name) => name !== 'integrations');
          return (
            <fieldset key={integration.key} className="space-y-2">
              <legend className="mb-2 flex items-center gap-2 text-sm">
                <IntegrationIcon name={integration.key} className="size-4" />
                {integration.title}
                {integration.connected ? null : <Badge tone="warn">Not connected</Badge>}
              </legend>
              {integration.scopes.length ? (
                <>
                  <div className="divide-y divide-line rounded-lg border border-line">
                    {integration.scopes.map((scope) => (
                      <ScopeBox
                        key={scope}
                        scope={scope}
                        description={scopes[scope] ?? ''}
                        on={chosen.includes(scope)}
                        onChange={toggle(scope)}
                        disabled={!integration.connected}
                        tools={toolLine(integration, scope)}
                      />
                    ))}
                  </div>
                </>
              ) : null}
              {picked ? (
                <div className="mt-3 grid gap-5 sm:grid-cols-2">
                  {integration.limits.map((limit) => {
                    const help = LIMIT_HINTS[limit] ?? {
                      label: limit,
                      placeholder: '',
                      hint: '',
                    };
                    const id = `${integration.key}.${limit}`;
                    return (
                      <Field key={id} label={help.label} hint={help.hint}>
                        <Input
                          value={limitText[id] ?? ''}
                          onChange={(e) => setLimitText({ ...limitText, [id]: e.target.value })}
                          placeholder={help.placeholder}
                        />
                      </Field>
                    );
                  })}
                </div>
              ) : null}
              {!integration.scopes.length ? (
                <p className="text-xs text-muted">
                  No agent tools.{usedBy.length ? ` Platform uses it for ${usedBy.join(', ')}.` : ''}
                </p>
              ) : null}
            </fieldset>
          );
        })}
        <FormActions error={create.error}>
          <Button variant="primary" disabled={create.isPending || !chosen.length}>
            Create token
          </Button>
          <Button type="button" variant="ghost" onClick={onDone}>
            Cancel
          </Button>
        </FormActions>
      </form>
  );
}

export function TokensPage() {
  const { org } = useCurrentOrg();
  const client = useQueryClient();
  const [adding, setAdding] = useState(false);
  const list = useQuery({
    queryKey: ['tokens', org?.id],
    queryFn: () => api<TokenList>(`/api/organizations/${org!.id}/tokens`),
    enabled: Boolean(org),
  });
  const revoke = useMutation({
    mutationFn: (id: number) => send(`/api/organizations/${org!.id}/tokens/${id}`, 'DELETE'),
    onSuccess: () => client.invalidateQueries({ queryKey: ['tokens', org?.id] }),
  });
  return (
    <>
      <PageHeader
        title="Tokens"
        description="Keys that apps and agents use to call Platform."
        docs="codebase/authentication"
        action={
          <Button variant="primary" onClick={() => setAdding(true)} disabled={!list.data}>
            <Plus className="size-4" /> New token
          </Button>
        }
      />
      <Dialog open={adding} onClose={() => setAdding(false)} title="New token" wide>
        {adding && org && list.data ? (
          <NewToken
            orgId={org.id}
            scopes={list.data.scopes}
            integrations={list.data.integrations ?? []}
            uses={list.data.uses ?? {}}
            onDone={() => setAdding(false)}
          />
        ) : null}
      </Dialog>
      {list.error ? (
        <div className="mb-4">
          <ErrorNote error={list.error} />
        </div>
      ) : null}
      <Card>
        {list.isLoading || !org ? (
          <SkeletonRows />
        ) : list.data?.tokens.length ? (
          <Table>
            <thead>
              <tr>
                <Th>Name</Th>
                <Th className="hidden md:table-cell">Token</Th>
                <Th className="hidden lg:table-cell">Last used</Th>
                <Th>
                  <span className="sr-only">Actions</span>
                </Th>
              </tr>
            </thead>
            <tbody>
              {list.data.tokens.map((t) => (
                <Tr key={t.id}>
                  <Td className="w-full max-w-0 py-3">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-medium">{t.name}</span>
                      <Badge>{t.kind}</Badge>
                    </div>
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {t.scopes.map((scope) => (
                        <Code key={scope} className="text-muted">
                          {scope}
                        </Code>
                      ))}
                      {Object.entries(t.limits ?? {}).flatMap(([integration, limits]) =>
                        Object.entries(limits).map(([name, values]) => (
                          <Code key={`${integration}.${name}`} className="text-muted">
                            {integration} {name}: {values.join(', ')}
                          </Code>
                        )),
                      )}
                    </div>
                  </Td>
                  <Td className="hidden whitespace-nowrap md:table-cell">
                    <Mono>{t.display}…</Mono>
                  </Td>
                  <Td className="hidden text-xs whitespace-nowrap text-muted tabular-nums lg:table-cell">{timeAgo(t.last_used_at)}</Td>
                  <Td className="text-right">
                    <DeleteButton
                      title="Revoke"
                      label={`Revoke ${t.name}`}
                      question={`Revoke ${t.name}? Anything using it stops working.`}
                      onDelete={() => revoke.mutate(t.id)}
                    />
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        ) : (
          <EmptyState icon={KeyRound} title="No active tokens" />
        )}
      </Card>
      <McpCard mcp={list.data?.mcp} />
    </>
  );
}

// How an agent reaches the tools of the org's modules: the MCP server, and a token from this page or OAuth.
function McpCard({ mcp }: { mcp?: TokenList['mcp'] }) {
  const [copied, setCopied] = useState(false);
  const url = mcp?.url ?? null;
  const rows: [string, string][] = [
    ['Server', url ?? '/mcp on port 8001'],
    ['Header', 'Authorization: Bearer plat_...'],
  ];
  return (
    <Card className="mt-6">
      <CardHeader title="MCP" />
      <dl className="divide-y divide-line text-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-center gap-3 px-4 py-2.5">
            <dt className="w-16 shrink-0 text-xs text-muted">{label}</dt>
            <dd className="min-w-0 truncate">
              <Code>{value}</Code>
            </dd>
            {label === 'Server' && url ? (
              <Button
                size="icon"
                className="ml-auto shrink-0"
                aria-label="Copy server URL"
                onClick={() => {
                  navigator.clipboard.writeText(url);
                  setCopied(true);
                }}
              >
                {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
              </Button>
            ) : null}
          </div>
        ))}
        <div className="flex items-start gap-3 px-4 py-2.5">
          <dt className="w-16 shrink-0 pt-0.5 text-xs text-muted">OAuth</dt>
          <dd className="min-w-0 space-y-1">
            <Badge tone={mcp?.oauth ? 'ok' : 'muted'}>{mcp?.oauth ? 'On' : 'Off'}</Badge>
            <p className="text-xs text-muted">
              {mcp?.oauth
                ? 'A client that supports OAuth needs only the server URL. An officer signs in with Discord and chooses the org, scopes and limits. Each connection shows above with the kind oauth.'
                : 'The server has no https API URL. Set REDIRECT_URI, ACCOUNTS_BASE_URL or MCP_PUBLIC_URL to let clients connect with OAuth.'}
            </p>
          </dd>
        </div>
      </dl>
    </Card>
  );
}
