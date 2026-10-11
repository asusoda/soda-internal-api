import { useMutation, useQuery } from '@tanstack/react-query';
import { History, Rocket, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { Button, Code, cx, Field, FormActions, Input, Mono, Spinner } from '../../components/ui';
import { send } from '../../lib/api';
import type { App, DeployPreview } from '../../lib/types';
import { providerTitle, useProviders } from './providers';
import { DEFAULT_MANIFEST_PATH, JsonBlock, Label, TAG_PATTERN, useInvalidate } from './shared';

export function DeployPanel({
  prefix,
  app,
  initialTag = '',
  onDone,
}: {
  prefix: string;
  app: App;
  initialTag?: string;
  onDone: () => void;
}) {
  const invalidate = useInvalidate(prefix);
  const host = providerTitle(useProviders(prefix).data, app.provider);
  const [tag, setTag] = useState(initialTag);
  const [ref, setRef] = useState('');
  const tagOk = !tag || TAG_PATTERN.test(tag);
  const body = (dryRun: boolean) => ({ tag, ...(app.repo && ref.trim() ? { ref: ref.trim() } : {}), dry_run: dryRun });
  const preview = useMutation({
    mutationFn: () => send<DeployPreview>(`/api/dashboard/${prefix}/apps/${app.name}/deploy`, 'POST', body(true)),
  });
  const deploy = useMutation({
    mutationFn: () => send(`/api/dashboard/${prefix}/apps/${app.name}/deploy`, 'POST', body(false)),
    onSuccess: () => {
      invalidate(app.name);
      onDone();
    },
  });
  const edit = (set: (v: string) => void) => (e: { target: { value: string } }) => {
    set(e.target.value.trim());
    preview.reset();
  };
  return (
    <form
      className="space-y-4 rounded-lg border border-line p-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (preview.isSuccess) deploy.mutate();
        else if (TAG_PATTERN.test(tag)) preview.mutate();
      }}
    >
      <div className={cx('grid gap-4', app.repo && 'sm:grid-cols-2')}>
        <Field label="Image tag" hint={tagOk ? 'A tag such as v1.2.0, or a sha256 digest.' : 'Not a valid tag or sha256 digest.'}>
          <Input value={tag} onChange={edit(setTag)} placeholder="v1.2.0" className="font-mono" aria-invalid={!tagOk} required autoFocus />
        </Field>
        {app.repo ? (
          <Field label="Git ref (optional)" hint={`The commit or branch to read ${app.manifest_path ?? DEFAULT_MANIFEST_PATH} at. Empty reads the default branch.`}>
            <Input value={ref} onChange={edit(setRef)} placeholder="main or a commit SHA" className="font-mono" />
          </Field>
        ) : null}
      </div>
      {preview.data ? (
        <div>
          <Label action={<Mono>{preview.data.request.method} {preview.data.request.path}</Mono>}>{host} request</Label>
          <JsonBlock value={preview.data.request.body} />
          <p className="mt-2 text-xs text-muted">
            {preview.data.request.method === 'POST'
              ? `Creates the pod. It starts billing on the org's ${host} account.`
              : 'Changes the image of the pod, which restarts it. The container disk is erased; volumes stay.'}
          </p>
        </div>
      ) : null}
      <FormActions error={preview.error ?? deploy.error}>
        {preview.isSuccess ? (
          <Button variant="primary" disabled={deploy.isPending}>
            {deploy.isPending ? <Spinner className="size-3.5" /> : <Rocket className="size-4" />}
            Deploy {tag}
          </Button>
        ) : (
          <Button variant="primary" disabled={!TAG_PATTERN.test(tag) || preview.isPending}>
            {preview.isPending ? <Spinner className="size-3.5" /> : null}
            Preview
          </Button>
        )}
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </FormActions>
    </form>
  );
}

export function RollbackPanel({ prefix, app, onDone }: { prefix: string; app: App; onDone: () => void }) {
  const invalidate = useInvalidate(prefix);
  const host = providerTitle(useProviders(prefix).data, app.provider);
  const preview = useQuery({
    queryKey: ['app-rollback', prefix, app.name, app.current_tag],
    queryFn: () => send<DeployPreview>(`/api/dashboard/${prefix}/apps/${app.name}/rollback`, 'POST', { dry_run: true }),
    retry: false,
    gcTime: 0,
  });
  const rollback = useMutation({
    mutationFn: () => send(`/api/dashboard/${prefix}/apps/${app.name}/rollback`, 'POST', {}),
    onSuccess: () => {
      invalidate(app.name);
      onDone();
    },
  });
  const target = preview.data?.tag;
  return (
    <div className="space-y-4 rounded-lg border border-line p-4">
      {preview.isLoading ? (
        <div className="flex items-center gap-2 text-sm text-muted">
          <Spinner /> Finding the last healthy deployment
        </div>
      ) : preview.data ? (
        <>
          <p className="text-sm text-pretty">
            Deploys <Code>{target ?? 'the previous tag'}</Code> again with the manifest it ran with
            {app.current_tag ? (
              <>
                , in place of <Code>{app.current_tag}</Code>
              </>
            ) : null}
            .
          </p>
          <div>
            <Label action={<Mono>{preview.data.request.method} {preview.data.request.path}</Mono>}>{host} request</Label>
            <JsonBlock value={preview.data.request.body} />
          </div>
        </>
      ) : null}
      <FormActions error={preview.error ?? rollback.error}>
        <Button variant="primary" disabled={!preview.isSuccess || rollback.isPending} onClick={() => rollback.mutate()}>
          {rollback.isPending ? <Spinner className="size-3.5" /> : <History className="size-4" />}
          Roll back{target ? ` to ${target}` : ''}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </FormActions>
    </div>
  );
}

export function DeletePanel({
  prefix,
  app,
  onDone,
  onDeleted,
}: {
  prefix: string;
  app: App;
  onDone: () => void;
  onDeleted: (name: string, podId: string | null) => void;
}) {
  const invalidate = useInvalidate(prefix);
  const host = providerTitle(useProviders(prefix).data, app.provider);
  const [typed, setTyped] = useState('');
  const remove = useMutation({
    mutationFn: () => send<{ deleted: boolean; pod_id: string | null }>(`/api/dashboard/${prefix}/apps/${app.name}`, 'DELETE'),
    onSuccess: (result) => {
      invalidate();
      onDeleted(app.name, result.pod_id);
    },
  });
  return (
    <form
      className="space-y-4 rounded-lg border border-bad/30 bg-bad/5 p-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (typed === app.name) remove.mutate();
      }}
    >
      <div className="space-y-1 text-sm text-pretty">
        <p className="font-medium">Delete {app.name} and its deployment history?</p>
        <p className="text-muted">
          {app.pod_id ? (
            <>
              The pod <Mono className="text-fg">{app.pod_id}</Mono> is not deleted. It keeps running and billing until you
              terminate it on {host}.
            </>
          ) : (
            `The app has no pod, so nothing runs on ${host}.`
          )}
        </p>
      </div>
      <Field label={`Type ${app.name} to confirm`}>
        <Input value={typed} onChange={(e) => setTyped(e.target.value)} className="font-mono" autoComplete="off" autoFocus />
      </Field>
      <FormActions error={remove.error}>
        <Button variant="danger" disabled={typed !== app.name || remove.isPending}>
          <Trash2 className="size-4" /> Delete app
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </FormActions>
    </form>
  );
}
