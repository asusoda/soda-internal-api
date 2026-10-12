import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  ArrowUp,
  ChevronRight,
  Download,
  File,
  Folder,
  FolderOpen,
  FolderPlus,
  Pencil,
  Power,
  RefreshCw,
  Save,
  Trash2,
  Upload,
} from 'lucide-react';
import { useRef, useState } from 'react';
import { useConfirm } from '../../components/confirm';
import {
  Button,
  cx,
  Dialog,
  EmptyState,
  ErrorNote,
  Input,
  Mono,
  SkeletonRows,
  Spinner,
  Table,
  Td,
  Textarea,
  Th,
  Tr,
} from '../../components/ui';
import { ApiError, api, apiBlob, send } from '../../lib/api';
import { bytes, timeAgo } from '../../lib/format';
import type { Pod, PodFile } from '../../lib/types';
import { podPath, usePodAction } from './shared';

const HOME = '/workspace';
const MAX_UPLOAD_BYTES = 100_000_000;

const join = (dir: string, name: string) => (dir === '/' ? `/${name}` : `${dir}/${name}`);
const parent = (dir: string) => dir.slice(0, dir.lastIndexOf('/')) || '/';

function notRunning(error: unknown) {
  return error instanceof ApiError && error.status === 409 && error.message.includes('not running');
}

// Saves a blob as a file through a temporary link.
function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function Breadcrumbs({ path, go }: { path: string; go: (p: string) => void }) {
  const parts = path.split('/').filter(Boolean);
  return (
    <nav aria-label="Folder" className="flex min-w-0 flex-1 items-center gap-0.5 overflow-x-auto font-mono text-xs">
      <button type="button" onClick={() => go('/')} className="shrink-0 cursor-pointer rounded px-1 py-0.5 text-muted hover:bg-panel-2 hover:text-fg">
        /
      </button>
      {parts.map((part, i) => {
        const target = `/${parts.slice(0, i + 1).join('/')}`;
        const last = i === parts.length - 1;
        return (
          <span key={target} className="flex shrink-0 items-center gap-0.5">
            {i ? <ChevronRight className="size-3 text-muted/60" /> : null}
            <button
              type="button"
              onClick={() => go(target)}
              aria-current={last ? 'page' : undefined}
              className={cx('cursor-pointer rounded px-1 py-0.5 hover:bg-panel-2', last ? 'font-medium text-fg' : 'text-muted hover:text-fg')}
            >
              {part}
            </button>
          </span>
        );
      })}
    </nav>
  );
}

// A one-field form for a new folder or a new name.
function NameForm({
  label,
  initial,
  submit,
  pending,
  error,
  onCancel,
}: {
  label: string;
  initial: string;
  submit: (name: string) => void;
  pending: boolean;
  error: unknown;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial);
  const valid = Boolean(name.trim()) && !name.includes('/') && name !== '.' && name !== '..';
  return (
    <form
      className="flex flex-wrap items-center gap-2 border-b border-line bg-panel-2/40 px-3 py-2.5"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) submit(name.trim());
      }}
    >
      <Input
        autoFocus
        aria-label={label}
        placeholder={label}
        value={name}
        onChange={(e) => setName(e.target.value)}
        className="h-8 min-w-40 flex-1 font-mono text-xs"
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            e.preventDefault();
            e.stopPropagation();
            onCancel();
          }
        }}
      />
      <Button variant="primary" disabled={!valid || pending}>
        {label.startsWith('New') ? 'Create' : 'Rename'}
      </Button>
      <Button type="button" variant="ghost" onClick={onCancel}>
        Cancel
      </Button>
      {error ? (
        <div className="w-full">
          <ErrorNote error={error} />
        </div>
      ) : null}
    </form>
  );
}

function Editor({ prefix, pod, path, onBack }: { prefix: string; pod: Pod; path: string; onBack: () => void }) {
  const base = podPath(prefix, pod.id);
  const [draft, setDraft] = useState<string | null>(null);
  const file = useQuery({
    queryKey: ['godfather', prefix, 'file', pod.id, path],
    queryFn: () => send<{ content: string }>(`${base}/files/read`, 'POST', { path }).then((b) => b.content),
    retry: false,
    gcTime: 0,
  });
  const write = useMutation({
    mutationFn: (content: string) => send(`${base}/files/write`, 'POST', { path, content }),
    onSuccess: () => file.refetch().then(() => setDraft(null)),
  });
  const download = useMutation({
    mutationFn: () => apiBlob(`${base}/files/download`, { method: 'POST', body: JSON.stringify({ path }) }),
    onSuccess: (blob) => save(blob, path.split('/').pop() || 'file'),
  });
  const value = draft ?? file.data ?? '';
  const changed = draft !== null && draft !== file.data;
  const tooLarge = file.error instanceof ApiError && file.error.status === 413;
  const confirm = useConfirm();
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="ghost"
          onClick={() => {
            if (!changed) {
              onBack();
              return;
            }
            void confirm('Discard your changes?', 'Discard').then((yes) => {
              if (yes) onBack();
            });
          }}
        >
          <ArrowLeft className="size-4" /> Back
        </Button>
        <Mono className="min-w-0 flex-1 truncate text-fg">{path}</Mono>
        <Button onClick={() => download.mutate()} disabled={download.isPending}>
          {download.isPending ? <Spinner className="size-3.5" /> : <Download className="size-4" />} Download
        </Button>
        <Button variant="primary" onClick={() => write.mutate(value)} disabled={!changed || write.isPending}>
          <Save className="size-4" /> {write.isPending ? 'Saving...' : 'Save'}
        </Button>
      </div>
      {file.isLoading ? (
        <div className="rounded-lg border border-line">
          <SkeletonRows rows={6} />
        </div>
      ) : file.error ? (
        <div className="rounded-lg border border-dashed border-line">
          <EmptyState icon={File} title={tooLarge ? 'Too large to edit here' : 'Cannot open this file'}>
            {(file.error as Error).message}
          </EmptyState>
        </div>
      ) : (
        <Textarea
          aria-label={`Contents of ${path}`}
          value={value}
          onChange={(e) => setDraft(e.target.value)}
          spellCheck={false}
          className="h-[55vh] resize-y font-mono text-xs leading-relaxed whitespace-pre"
        />
      )}
      {write.error ? <ErrorNote error={write.error} /> : null}
      {download.error ? <ErrorNote error={download.error} /> : null}
      {changed ? <p className="text-xs text-muted">Unsaved changes. Save replaces the file on the pod.</p> : null}
    </div>
  );
}

type Pending = { kind: 'mkdir' } | { kind: 'rename'; entry: PodFile } | null;

export function FilesDialog({ prefix, pod, onClose }: { prefix: string; pod: Pod; onClose: () => void }) {
  const base = podPath(prefix, pod.id);
  const client = useQueryClient();
  const [path, setPath] = useState(HOME);
  const [opened, setOpened] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending>(null);
  const upload = useRef<HTMLInputElement>(null);
  const start = usePodAction(prefix, pod.id);
  const confirm = useConfirm();
  const list = useQuery({
    queryKey: ['godfather', prefix, 'files', pod.id, path],
    queryFn: () => api<{ path: string; files: PodFile[] }>(`${base}/files?path=${encodeURIComponent(path)}`).then((b) => b.files),
    retry: false,
  });
  const reload = () => client.invalidateQueries({ queryKey: ['godfather', prefix, 'files', pod.id] });
  const go = (p: string) => {
    setPath(p);
    setPending(null);
  };
  const mkdir = useMutation({
    mutationFn: (name: string) => send(`${base}/files/mkdir`, 'POST', { path: join(path, name) }),
    onSuccess: () => {
      setPending(null);
      reload();
    },
  });
  const rename = useMutation({
    mutationFn: ({ from, to }: { from: string; to: string }) => send(`${base}/files/rename`, 'POST', { old_path: from, new_path: to }),
    onSuccess: () => {
      setPending(null);
      reload();
    },
  });
  const remove = useMutation({
    mutationFn: (target: string) => send(`${base}/files/delete`, 'POST', { path: target }),
    onSuccess: reload,
  });
  const put = useMutation({
    mutationFn: (file: globalThis.File) => {
      if (file.size > MAX_UPLOAD_BYTES) throw new Error('Uploads are limited to 100 MB.');
      const form = new FormData();
      form.append('file', file);
      form.append('path', path);
      return api(`${base}/files/upload`, { method: 'POST', body: form });
    },
    onSuccess: reload,
  });
  const download = useMutation({
    mutationFn: (target: string) => apiBlob(`${base}/files/download`, { method: 'POST', body: JSON.stringify({ path: target }) }),
    onSuccess: (blob, target) => save(blob, target.split('/').pop() || 'file'),
  });
  const actionError = remove.error ?? put.error ?? download.error;
  const stopped = notRunning(list.error);

  return (
    <Dialog open onClose={onClose} wide title={`Files on ${pod.name}`} description="Only the volume is kept when the pod stops.">
      {opened ? (
        <Editor prefix={prefix} pod={pod} path={opened} onBack={() => setOpened(null)} />
      ) : stopped ? (
        <div className="rounded-lg border border-dashed border-line">
          <EmptyState
            icon={Power}
            title="The pod is not running"
            action={
              <Button
                variant="primary"
                disabled={start.isPending}
                onClick={() => start.mutate('start', { onSuccess: () => setTimeout(reload, 5000) })}
              >
                {start.isPending ? <Spinner className="size-3.5" /> : <Power className="size-4" />} Start pod
              </Button>
            }
          >
            Files can be read only while the pod runs. A pod takes a minute or two to boot after it starts.
            {start.error ? <div className="mt-3"><ErrorNote error={start.error} /></div> : null}
          </EmptyState>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex min-w-0 flex-1 basis-60 items-center gap-1 rounded-md border border-line bg-panel-2/40 px-1.5 py-1">
              <Button variant="ghost" size="icon" className="size-6" aria-label="Up one folder" title="Up" disabled={path === '/'} onClick={() => go(parent(path))}>
                <ArrowUp className="size-3.5" />
              </Button>
              <Breadcrumbs path={path} go={go} />
            </div>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="icon" aria-label="Refresh" title="Refresh" onClick={reload}>
                <RefreshCw className={cx('size-4', list.isFetching && 'animate-spin')} />
              </Button>
              <Button onClick={() => setPending({ kind: 'mkdir' })}>
                <FolderPlus className="size-4" /> <span className="hidden sm:inline">New folder</span>
              </Button>
              <Button onClick={() => upload.current?.click()} disabled={put.isPending}>
                {put.isPending ? <Spinner className="size-3.5" /> : <Upload className="size-4" />}
                <span className="hidden sm:inline">{put.isPending ? 'Uploading...' : 'Upload'}</span>
              </Button>
              <input
                ref={upload}
                type="file"
                className="hidden"
                aria-label="Upload a file"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) put.mutate(file);
                  e.target.value = '';
                }}
              />
            </div>
          </div>
          {actionError ? <ErrorNote error={actionError} /> : null}
          <div className="overflow-hidden rounded-lg border border-line">
            {pending?.kind === 'mkdir' ? (
              <NameForm label="New folder name" initial="" submit={(name) => mkdir.mutate(name)} pending={mkdir.isPending} error={mkdir.error} onCancel={() => setPending(null)} />
            ) : pending?.kind === 'rename' ? (
              <NameForm
                key={pending.entry.name}
                label={`Rename ${pending.entry.name}`}
                initial={pending.entry.name}
                submit={(name) => rename.mutate({ from: join(path, pending.entry.name), to: join(path, name) })}
                pending={rename.isPending}
                error={rename.error}
                onCancel={() => setPending(null)}
              />
            ) : null}
            {list.isLoading ? (
              <SkeletonRows rows={5} />
            ) : list.error ? (
              <div className="p-4">
                <ErrorNote error={list.error} />
              </div>
            ) : list.data?.length ? (
              <Table>
                <thead>
                  <tr>
                    <Th>Name</Th>
                    <Th className="hidden text-right sm:table-cell">Size</Th>
                    <Th className="hidden md:table-cell">Modified</Th>
                    <Th>
                      <span className="sr-only">Actions</span>
                    </Th>
                  </tr>
                </thead>
                <tbody>
                  {list.data.map((entry) => {
                    const dir = entry.type === 'directory';
                    const target = join(path, entry.name);
                    const modified = entry.modified ? new Date(entry.modified * 1000) : null;
                    return (
                      <Tr key={entry.name}>
                        <Td className="h-10 w-full max-w-0">
                          <button
                            type="button"
                            onClick={() => (dir ? go(target) : setOpened(target))}
                            className="flex max-w-full cursor-pointer items-center gap-2 rounded-sm text-left hover:underline"
                            title={dir ? `Open ${entry.name}` : `Edit ${entry.name}`}
                          >
                            {dir ? <Folder className="size-4 shrink-0 text-info" /> : <File className="size-4 shrink-0 text-muted" />}
                            <span className="truncate">{entry.name}</span>
                          </button>
                        </Td>
                        <Td className="hidden h-10 text-right text-xs whitespace-nowrap text-muted tabular-nums sm:table-cell">
                          {dir ? '-' : bytes(entry.size)}
                        </Td>
                        <Td
                          className="hidden h-10 text-xs whitespace-nowrap text-muted tabular-nums md:table-cell"
                          title={modified?.toLocaleString()}
                        >
                          {modified ? timeAgo(modified.toISOString()) : '-'}
                        </Td>
                        <Td className="h-10 py-1 pr-2 pl-0">
                          <div className="flex items-center justify-end">
                            {dir ? null : (
                              <Button variant="ghost" size="icon" aria-label={`Download ${entry.name}`} title="Download" onClick={() => download.mutate(target)}>
                                <Download className="size-4" />
                              </Button>
                            )}
                            <Button variant="ghost" size="icon" aria-label={`Rename ${entry.name}`} title="Rename" onClick={() => setPending({ kind: 'rename', entry })}>
                              <Pencil className="size-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="hover:text-bad"
                              aria-label={`Delete ${entry.name}`}
                              title="Delete"
                              disabled={remove.isPending}
                              onClick={() => {
                                const question = dir ? `Delete ${target} and everything in it?` : `Delete ${target}?`;
                                void confirm(question, 'Delete').then((yes) => {
                                  if (yes) remove.mutate(target);
                                });
                              }}
                            >
                              <Trash2 className="size-4" />
                            </Button>
                          </div>
                        </Td>
                      </Tr>
                    );
                  })}
                </tbody>
              </Table>
            ) : (
              <EmptyState icon={FolderOpen}>This folder is empty.</EmptyState>
            )}
          </div>
          <p className="text-xs text-muted">Click a file to edit it as text, up to 1 MB. Uploads and downloads go up to 100 MB.</p>
        </div>
      )}
    </Dialog>
  );
}
