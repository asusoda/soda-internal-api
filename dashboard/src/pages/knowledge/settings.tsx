import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { RefreshCw, RotateCcw } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';
import { Badge, Button, CheckOption, ErrorNote, Field, FormActions, Input, Select, SkeletonRows, Spinner } from '../../components/ui';
import { api, send } from '../../lib/api';
import type { EmbeddingStatus, KnowledgeMode, KnowledgeSettings, KnowledgeTuning } from '../../lib/types';

// Limits from modules/knowledge/settings.py.
const LIMITS: Record<Exclude<keyof KnowledgeTuning, 'mode'>, [number, number]> = {
  chunk_chars: [100, 4000],
  chunk_overlap: [0, 2000],
  top_k: [1, 50],
  window: [0, 5],
  max_distance: [0.05, 2],
  rrf_k: [1, 200],
};

const MODES: { value: KnowledgeMode; label: string }[] = [
  { value: 'hybrid', label: 'Hybrid: vectors and text, fused' },
  { value: 'text', label: 'Text only: word match' },
  { value: 'vector', label: 'Vectors only: meaning match' },
];

type Draft = Record<keyof KnowledgeTuning, string>;

function toDraft(t: KnowledgeTuning): Draft {
  return Object.fromEntries(Object.entries(t).map(([k, v]) => [k, String(v)])) as Draft;
}

// How many passages are on the current embedding model, and a button that embeds the rest from their stored text.
function EmbeddingRow({ prefix, status }: { prefix: string; status: EmbeddingStatus }) {
  const run = useMutation({ mutationFn: () => send(`/api/dashboard/${prefix}/knowledge/reembed`, 'POST') });
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-md border border-line px-3 py-2.5 text-xs">
      <span className="min-w-0 flex-1 text-pretty text-muted">
        {status.stale
          ? `${status.embedded} of ${status.passages} passages use ${status.model}. Text search still finds the other ${status.stale}.`
          : `All ${status.passages} passages use ${status.model}.`}
      </span>
      {status.stale ? (
        run.isSuccess ? (
          <span className="text-ok">Embedding in the background.</span>
        ) : (
          <Button type="button" disabled={run.isPending} onClick={() => run.mutate()}>
            {run.isPending ? <Spinner className="size-3.5" /> : <RefreshCw className="size-3.5" />} Embed {status.stale}
          </Button>
        )
      ) : null}
      {run.error ? <ErrorNote error={run.error} /> : null}
    </div>
  );
}

export function KnowledgeSettingsForm({ prefix, onDone }: { prefix: string; onDone: (message: string | null) => void }) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ['knowledge', prefix, 'settings'],
    queryFn: () => api<KnowledgeSettings>(`/api/dashboard/${prefix}/knowledge/settings`),
  });
  if (query.isLoading || !query.data) return <SkeletonRows />;
  return (
    <SettingsDraft
      prefix={prefix}
      data={query.data}
      onSaved={(next, reindex) => {
        client.setQueryData(['knowledge', prefix, 'settings'], next);
        onDone(reindex ? 'Saved. A job is crawling every crawled source again with the new passage size.' : 'Saved.');
      }}
      onCancel={() => onDone(null)}
    />
  );
}

function SettingsDraft({
  prefix,
  data,
  onSaved,
  onCancel,
}: {
  prefix: string;
  data: KnowledgeSettings;
  onSaved: (next: KnowledgeSettings, reindexed: boolean) => void;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState<Draft>(toDraft(data.settings));
  const [reindex, setReindex] = useState(false);
  const number = (k: keyof typeof LIMITS) => Number(draft[k]);
  const valid = (k: keyof typeof LIMITS) => {
    const [lo, hi] = LIMITS[k];
    const n = number(k);
    return draft[k] !== '' && Number.isFinite(n) && n >= lo && n <= hi && (k === 'max_distance' || Number.isInteger(n));
  };
  const overlapOk = number('chunk_overlap') <= Math.floor(number('chunk_chars') / 2);
  const allOk = (Object.keys(LIMITS) as (keyof typeof LIMITS)[]).every(valid) && overlapOk;
  const chunking = draft.chunk_chars !== String(data.settings.chunk_chars) || draft.chunk_overlap !== String(data.settings.chunk_overlap);

  const save = useMutation({
    mutationFn: async () => {
      const body = {
        mode: draft.mode,
        ...Object.fromEntries((Object.keys(LIMITS) as (keyof typeof LIMITS)[]).map((k) => [k, number(k)])),
      };
      const next = await send<KnowledgeSettings>(`/api/dashboard/${prefix}/knowledge/settings`, 'PUT', body);
      if (reindex) await send(`/api/dashboard/${prefix}/knowledge/reindex`, 'POST');
      return next;
    },
    onSuccess: (next) => onSaved(next, reindex),
  });

  const field = (k: keyof typeof LIMITS, label: string, hint: string, step = 1) => (
    <Field label={label} hint={valid(k) ? `${hint} Default ${data.defaults[k]}.` : `From ${LIMITS[k][0]} to ${LIMITS[k][1]}.`}>
      <Input
        type="number"
        min={LIMITS[k][0]}
        max={LIMITS[k][1]}
        step={step}
        value={draft[k]}
        onChange={(e) => setDraft({ ...draft, [k]: e.target.value })}
        aria-invalid={!valid(k)}
      />
    </Field>
  );

  return (
    <form
      className="space-y-6"
      onSubmit={(e) => {
        e.preventDefault();
        if (allOk) save.mutate();
      }}
    >
      <section className="space-y-4">
        <h3 className="text-sm font-medium">Index</h3>
        <div className="grid gap-5 sm:grid-cols-2">
          {field('chunk_chars', 'Passage size (characters)', 'Longer passages give more context per hit and fewer hits.', 50)}
          {field('chunk_overlap', 'Overlap (characters)', 'Text repeated from the end of the passage before.', 25)}
        </div>
        {!overlapOk ? <p className="text-xs text-bad">Overlap must be at most half the passage size.</p> : null}
        <p className="text-xs text-pretty text-muted">
          A new passage size applies the next time a source is indexed. Upload a document again to split it again.
        </p>
        {chunking ? (
          <CheckOption checked={reindex} onChange={setReindex} title="Crawl every crawled source again now">
            Pages are fetched one host at a time; shared content with many pages takes a while.
          </CheckOption>
        ) : null}
      </section>

      <section className="space-y-4 border-t border-line pt-5">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium">Search</h3>
          {data.embeddings.configured ? (
            <Badge tone="ok">embeddings: {data.embeddings.model}</Badge>
          ) : (
            <Badge tone="warn">no embedding service</Badge>
          )}
        </div>
        {data.embeddings.configured && data.embeddings.status ? <EmbeddingRow prefix={prefix} status={data.embeddings.status} /> : null}
        {!data.embeddings.configured ? (
          <p className="text-xs text-pretty text-muted">
            Without an embedding service, every mode searches on text only. Connect one in{' '}
            <Link to={`/${prefix}/explore?tab=integrations`} className="text-accent hover:underline">
              Integrations &gt; Embeddings
            </Link>
            .
          </p>
        ) : null}
        <Field label="Mode" hint="Hybrid finds exact words and paraphrases.">
          <Select value={draft.mode} onChange={(e) => setDraft({ ...draft, mode: e.target.value })}>
            {MODES.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </Select>
        </Field>
        <div className="grid gap-5 sm:grid-cols-2">
          {field('top_k', 'Results per search', 'Used when the caller sends no top_k.')}
          {field('window', 'Neighbor passages', 'Passages added on each side of a hit, for context.')}
          {field('max_distance', 'Vector distance limit', 'Cosine distance. Lower is stricter.', 0.05)}
          {field('rrf_k', 'Fusion constant (k)', 'Higher gives lower-ranked hits more weight.')}
        </div>
      </section>

      <FormActions error={save.error}>
        <Button variant="primary" disabled={!allOk || save.isPending}>
          {save.isPending ? <Spinner className="size-3.5" /> : reindex ? <RefreshCw className="size-4" /> : null}
          {reindex ? 'Save and reindex' : 'Save'}
        </Button>
        <Button type="button" variant="ghost" onClick={() => setDraft(toDraft(data.defaults))}>
          <RotateCcw className="size-4" /> Defaults
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </FormActions>
    </form>
  );
}
