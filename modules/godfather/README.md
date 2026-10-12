# godfather

Runs GPU and CPU pods on an org's own hosting provider account that members connect to over SSH. Each pod keeps its `provider`, and calls go through `core/hosting.py`. RunPod is the only provider Godfather uses: its pods need SSH. Officers create, share, start, stop and schedule pods and manage their files. Members get a short-lived SSH certificate from the Godfather CLI.

Terminate also forgets a pod that was already deleted on RunPod, such as one deleted in the RunPod console.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Officer routes under `/<org_prefix>/pods` and the member list and search at `/<org_prefix>/members` and `/<org_prefix>/members/roles`, member routes under `/<org_prefix>/me`, and the CLI sign-in through Discord |
| `tools.py` | The `godfather.*` tools for agents |
| `service.py` | Pods on their provider, sharing and member connect |
| `ssh.py` | The org's SSH keys and short-lived certificates |
| `files.py` | File operations on a pod over SFTP, as root with the org's backend key |
| `presence.py` | Live SSH sessions on a pod, read with `ps` over the same root connection |
| `schedule.py` | Sessions: start a pod before a session and stop it after |
| `cli_login.py` | The CLI machine token (kind `cli`, scope `godfather:connect`) for a member |
| `models.py`, `jobs.py` | Pods, SSH keys, sessions and connections; the schedule job |

## Surface

- Routes: `/api/compute`, behind the `godfather` switch. The prefix and the `compute_*` tables keep the old module name, because the Godfather CLI calls these routes. Officer routes need an officer of the org. Member routes need a Discord session or a CLI token with `godfather:connect`.
- Jobs: `godfather.schedule`, schedule `*/5 * * * *`.
- Limits: `godfather.pods`, checked before a pod is made. See [docs/limits.md](../../docs/limits.md).
- Tools, scope `godfather:manage`: `godfather.pods`, `godfather.pod_members`, `godfather.connected`, `godfather.pod_action` (confirm), `godfather.create_pod` (confirm), `godfather.update_pod`, `godfather.settings`, `godfather.update_settings`, `godfather.sessions`, `godfather.add_session` (confirm), `godfather.delete_session`, `godfather.list_files`, `godfather.read_file`, `godfather.write_file` (confirm), `godfather.make_folder`, `godfather.move_file`, `godfather.delete_file` (confirm). Tools marked confirm run only with `confirm=true`.
- Webhook events: `pod.started` and `pod.stopped`, from `act()` and the session schedule. See [docs/webhooks.md](../../docs/webhooks.md).
- Tables: `compute_pods`, `compute_keys`, `compute_sessions`, `compute_connections`. `connect()` writes a `compute_connections` row for each certificate and deletes the org's rows older than 90 days.

See [docs/modules/godfather.md](../../docs/modules/godfather.md) for setup, `GODFATHER_CLI_NAME`, `GODFATHER_POD_IMAGE`, the org default pod image and the pod image contract.
