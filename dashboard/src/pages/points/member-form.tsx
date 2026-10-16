import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Button, Dialog, Field, FormActions, Input } from '../../components/ui';
import { send } from '../../lib/api';
import type { PointsMember } from '../../lib/types';
import { memberChanges, memberKey } from './shared';

const EMPTY = { email: '', name: '', asu_id: '', academic_standing: '', major: '' };

// Adds a member when member is null, else edits the member's details.
export function MemberDialog({
  prefix,
  member,
  open,
  onClose,
}: {
  prefix: string;
  member: PointsMember | null;
  open: boolean;
  onClose: () => void;
}) {
  const client = useQueryClient();
  const [draft, setDraft] = useState(EMPTY);
  useEffect(() => {
    if (!open) return;
    setDraft(
      member
        ? {
            email: member.email ?? '',
            name: member.name ?? '',
            asu_id: member.asu_id ?? '',
            academic_standing: member.academic_standing ?? '',
            major: member.major ?? '',
          }
        : EMPTY,
    );
  }, [open, member]);
  const save = useMutation({
    mutationFn: () => {
      const fields = { name: draft.name, asu_id: draft.asu_id, academic_standing: draft.academic_standing, major: draft.major };
      return member
        ? send(`/api/points/${prefix}/users/${encodeURIComponent(memberKey(member))}`, 'PUT', memberChanges(member, fields))
        : send(`/api/points/${prefix}/users`, 'POST', {
            email: draft.email,
            ...Object.fromEntries(Object.entries(fields).filter(([, v]) => v)),
          });
    },
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['points', prefix] });
      onClose();
    },
  });
  const set = (k: keyof typeof draft) => (e: { target: { value: string } }) => setDraft({ ...draft, [k]: e.target.value });
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={member ? 'Edit member' : 'Add member'}
      description={member ? (member.email ?? undefined) : 'Add a member to the org by email. A known email adds that person.'}
    >
      <form
        className="space-y-5"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        {member ? null : (
          <Field label="Email">
            <Input type="email" value={draft.email} onChange={set('email')} placeholder="ada@example.edu" required autoFocus />
          </Field>
        )}
        <Field label="Name">
          <Input value={draft.name} onChange={set('name')} required={!member} autoFocus={Boolean(member)} />
        </Field>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Student ID" hint="Optional.">
            <Input value={draft.asu_id} onChange={set('asu_id')} />
          </Field>
          <Field label="Class standing" hint="Optional.">
            <Input value={draft.academic_standing} onChange={set('academic_standing')} placeholder="Junior" />
          </Field>
        </div>
        <Field label="Major" hint="Optional.">
          <Input value={draft.major} onChange={set('major')} />
        </Field>
        <FormActions error={save.error}>
          <Button variant="primary" disabled={save.isPending || (!member && (!draft.email || !draft.name))}>
            {member ? 'Save' : 'Add member'}
          </Button>
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </FormActions>
      </form>
    </Dialog>
  );
}
