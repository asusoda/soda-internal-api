import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { Button, cx, Field, FormActions, Input, Spinner } from '../../components/ui';
import { send } from '../../lib/api';
import type { App } from '../../lib/types';
import { firstConfigured, ProviderField, useProviders } from './providers';
import { ManifestInput, readManifest } from './manifest';
import { DEFAULT_MANIFEST_PATH, NAME_PATTERN, REPO_PATTERN, useInvalidate } from './shared';

type Source = 'repo' | 'inline';

function SourceChoice({ value, onChange }: { value: Source; onChange: (v: Source) => void }) {
  const options: { id: Source; title: string; text: string }[] = [
    { id: 'repo', title: 'From repository', text: 'Read platform.app.yaml at each deploy, reviewed like code.' },
    { id: 'inline', title: 'Inline manifest', text: 'Keep the manifest here and edit it in the dashboard.' },
  ];
  return (
    <fieldset>
      <legend className="mb-1.5 text-sm font-medium">Manifest source</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {options.map((o) => (
          <label
            key={o.id}
            className={cx(
              'flex cursor-pointer items-start gap-2.5 rounded-lg border p-3 text-sm transition-colors has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-ring',
              value === o.id ? 'border-fg/40 bg-panel-2' : 'border-line hover:bg-panel-2/50',
            )}
          >
            <input
              type="radio"
              name="manifest-source"
              className="mt-0.5 size-4 accent-current"
              checked={value === o.id}
              onChange={() => onChange(o.id)}
            />
            <span className="min-w-0">
              <span className="block font-medium">{o.title}</span>
              <span className="mt-0.5 block text-xs text-muted">{o.text}</span>
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

// existing holds the names of the apps of the org.
export function RegisterApp({
  prefix,
  existing,
  onDone,
}: {
  prefix: string;
  existing: string[];
  onDone: (name: string | null) => void;
}) {
  const invalidate = useInvalidate(prefix);
  const [name, setName] = useState('');
  const [source, setSource] = useState<Source>('repo');
  const [repo, setRepo] = useState('');
  const [path, setPath] = useState(DEFAULT_MANIFEST_PATH);
  const [text, setText] = useState('');
  const providers = useProviders(prefix);
  const [chosen, setChosen] = useState<string | null>(null);
  const provider = chosen ?? firstConfigured(providers.data);
  const nameOk = !name || NAME_PATTERN.test(name);
  const repoOk = !repo || REPO_PATTERN.test(repo);
  const parsed = readManifest(text);
  const taken = existing.includes(name);
  const ready = !taken && NAME_PATTERN.test(name) && (source === 'repo' ? REPO_PATTERN.test(repo) && path.trim() : parsed.manifest);
  const create = useMutation({
    mutationFn: () =>
      send<App>(
        `/api/dashboard/${prefix}/apps/${name}`,
        'PUT',
        source === 'repo'
          ? { provider, repo, manifest_path: path.trim() || DEFAULT_MANIFEST_PATH }
          : { provider, manifest: parsed.manifest },
      ),
    onSuccess: () => {
      invalidate(name);
      onDone(name);
    },
  });
  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        if (ready) create.mutate();
      }}
    >
      <Field label="Name" hint={
          nameOk
            ? provider === 'server'
              ? `Lowercase letters, digits and dashes. The container is named app-${prefix}-${name || '<name>'}.`
              : `Lowercase letters, digits and dashes. The pod is named ${prefix}-${name || '<name>'}.`
            : 'Use lowercase letters, digits and dashes, starting with a letter or digit.'
        }>
        <Input value={name} onChange={(e) => setName(e.target.value.trim())} placeholder="club-bot" aria-invalid={!nameOk} required autoFocus />
      </Field>
      <ProviderField
        prefix={prefix}
        providers={providers.data}
        value={provider}
        onChange={setChosen}
        hint=""
      />
      <SourceChoice value={source} onChange={setSource} />
      {source === 'repo' ? (
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Repository" hint={repoOk ? 'owner/name. Private repos need GitHub on Integrations.' : 'Use the form owner/name.'}>
            <Input value={repo} onChange={(e) => setRepo(e.target.value.trim())} placeholder="example-club/club-bot" aria-invalid={!repoOk} required />
          </Field>
          <Field label="Manifest path">
            <Input value={path} onChange={(e) => setPath(e.target.value)} className="font-mono" required />
          </Field>
        </div>
      ) : (
        <ManifestInput value={text} onChange={setText} />
      )}
      <FormActions error={taken ? `An app named ${name} exists.` : create.error}>
        <Button variant="primary" disabled={!ready || create.isPending}>
          {create.isPending ? <Spinner className="size-3.5" /> : null}
          Register app
        </Button>
        <Button type="button" variant="ghost" onClick={() => onDone(null)}>
          Cancel
        </Button>
      </FormActions>
    </form>
  );
}
