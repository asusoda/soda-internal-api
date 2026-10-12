# Godfather

GPU and CPU pods on an org's own hosting provider account that members connect to over SSH with a Godfather CLI. RunPod is the only provider that Godfather can use: its pods need SSH. The reference CLI is `godfather` (`pip install godfather-cli`). Officers create pods and select who can use them. A member gets a certificate for their own SSH key that works on one pod for 12 hours.

## Setup

1. Connect RunPod on the Integrations tab of the dashboard Explore page. This saves the org secret `runpod_api_key`. The runpod module uses the same key. `SECRETS_KEY` must be set.
2. Add the `godfather` module on Explore for the org.
3. Optional: set these in Doppler.
   - `GODFATHER_CLI_NAME`: the CLI name in sign-in pages and errors. Default `godfather`. The old name `COMPUTE_CLI_NAME` still works.
   - `GODFATHER_POD_IMAGE`: the deployment default pod image. The old name `COMPUTE_POD_IMAGE` still works. Default `ghcr.io/theaisocietyasu/godfather-base:latest`.
4. Optional: set the org's own default pod image under Godfather > Settings on the dashboard (`PUT /api/compute/<org>/settings` with `{"pod_image": "..."}`, null to clear). A pod gets the image of its create body, else the org default, else `GODFATHER_POD_IMAGE`.

The first pod makes two ed25519 key pairs for the org in `compute_keys`. `SECRETS_KEY` encrypts the private keys.

- `backend`: its public key goes into root's `authorized_keys` on each pod.
- `user_ca`: pods trust it through `TrustedUserCAKeys`. It signs member and officer certificates.

The pod image must do this setup. It reads `GODFATHER_SSH_PUBLIC_KEY`, `GODFATHER_SSH_CA_PUBLIC_KEY` and `GODFATHER_SETUP` from its env. It accepts certificates with the principal `gf-<pod_id>`. It has `/usr/local/bin/godfather-login`. These names do not change with `GODFATHER_CLI_NAME`.

## Officer routes

All routes are under `/api/compute/<org>` and need an officer of the org. The prefix keeps the old module name `compute`, because the Godfather CLI calls it.

| Route | Does |
| --- | --- |
| `GET /pods` | Pods made here, with `provider` and the live status from the provider |
| `POST /pods` | Creates a pod. Body below. 201 |
| `GET /pods/<pod_id>` | One pod |
| `PUT /pods/<pod_id>` | `{"is_public": true}`, `{"allowed_users": ["<discord id>", ...]}`, or both |
| `GET /members?q=&role=&limit=` | Server members for `allowed_users`, sorted by name, bots left out: `members` (`id`, `name`, `username`, `avatar`, `roles`) and `total`. `q` searches usernames and server nicknames that start with it. Without `q` the whole member list is read, which needs the Server Members intent on the bot. `role` keeps the holders of one role. `limit` is 1 to 500, default 50 |
| `GET /members/roles` | Server roles to filter by, highest first, without the everyone role and roles that bots manage: `id`, `name`, `color` |
| `GET /members?ids=<id>,<id>` | The display names of up to 50 ids. 503 when Discord does not answer |
| `POST /pods/<pod_id>/action` | `{"action": "start" \| "stop" \| "restart" \| "terminate"}`. `terminate` deletes the pod and its record |

All fields of the create body are optional. `provider` names the hosting provider, default `runpod`. An unknown name answers 400. Platform sends the other fields to the RunPod v2 API. A GPU pod gets a volume when `volume_in_gb` is 10 or more. A CPU pod has no volume, and `vcpu_count` is a power of two. When RunPod refuses the request, the route answers 400 with RunPod's reason. When RunPod fails, it answers 424.

```json
{
  "provider": "runpod",
  "name": "workshop",
  "image_name": "ghcr.io/theaisocietyasu/godfather-base:latest",
  "gpu_type_id": "NVIDIA RTX A4000",
  "use_cpu_only": false,
  "cpu_flavor": "cpu3c",
  "vcpu_count": 2,
  "cloud_type": "COMMUNITY",
  "volume_in_gb": 0,
  "container_disk_in_gb": 20,
  "volume_mount_path": "/workspace",
  "env": {"HF_HOME": "/workspace/hf"},
  "is_public": false,
  "allowed_users": []
}
```

## Member routes

These routes need a Discord session, or the CLI token as `Authorization: Bearer plat_...`. Each request checks that the caller is a member of the org's server.

| Route | Does |
| --- | --- |
| `GET /api/compute/<org>/me/pods` | Running pods that are public or that list the member in `allowed_users` |
| `POST /api/compute/<org>/me/pods/<pod_id>/connect` | `{"public_key": "ssh-ed25519 ..."}`. Returns host, port, `user_folder` and a certificate |

A member certificate has the principal `gf-<pod_id>` and forces `/usr/local/bin/godfather-login <username>`, which puts the member in their own account and folder. An officer of the org gets a root certificate with no forced command. A certificate is valid from 5 minutes ago to 12 hours from now. The audit log records each connect, and the `compute_connections` table keeps it for the pod's member list.

## Who is on a pod

Officers see who can connect to a pod, who connected and who is connected now. On the dashboard, open a pod's Members from its row on the Godfather page.

| Route | Does |
| --- | --- |
| `GET .../pods/<pod_id>/members` | `access`: `is_public` and the `allowed` members (`discord_id`, `name`). `recent`: the last 100 certificates for the pod, newest first (`discord_id`, `name`, `username`, `is_admin`, `created_at`) |
| `GET .../pods/<pod_id>/members/connected` | The live SSH sessions on the pod: `state` (`known` or `unknown`), `reason`, and `sessions` (`username`, `is_admin`, `seconds`, `discord_id`, `name`) |

Names come from the org's Discord server, for at most 50 members in each request. Other names are null. `connect` writes one `compute_connections` row for each certificate. A new row deletes the org's rows older than 90 days. Terminate deletes the pod's rows.

The connected route opens SSH to the pod as root with the `backend` key, with a 5 second limit. It runs `ps` and finds the `su - godfather_<username>` process of each member session and the `/etc/godfather/admin.bashrc` shell of each officer session, which has `GODFATHER_USER` in its environment. It maps a username to the member who last got a certificate with it for the pod. The answer is always 200. The state is `unknown`, with a reason, when the pod is stopped, SSH fails, or the pod has no `/usr/local/bin/godfather-login`. A root SSH login that does not go through `godfather-login` is not shown.

## CLI sign-in

1. `<cli> auth` opens `GET /api/compute/<org>/cli/login`, which sends the member to Discord.
2. Discord returns to `GET /api/compute/cli/callback`. If the member is in the org's server and compute is on, the page shows a token one time.
3. The member pastes the token into the CLI. The CLI sends it on the member routes.

The CLI signs in one time, then gets a certificate each time it connects.

```mermaid
sequenceDiagram
  participant CLI as Godfather CLI
  participant API as Platform
  participant D as Discord
  participant Pod as Pod
  CLI->>API: GET /api/compute/org/cli/login
  API->>D: Send the member to sign in
  D->>API: GET /api/compute/cli/callback
  API-->>CLI: Token shown one time, pasted into the CLI
  CLI->>API: GET /api/compute/org/me/pods
  API-->>CLI: Running pods the member can use
  CLI->>API: POST .../me/pods/pod_id/connect with public_key
  API-->>CLI: Host, port, user_folder, certificate
  CLI->>Pod: SSH with the certificate
  Pod->>Pod: godfather-login username
```

The token is a machine token of kind `cli` with the scope `godfather:connect`, for the member's Discord id and the org. It is valid for 90 days. A new sign-in revokes the member's previous CLI token. The audit log records each token.

The CLI sign-in needs `ACCOUNTS_BASE_URL`, `CLIENT_ID` and `CLIENT_SECRET` on the server, and `<ACCOUNTS_BASE_URL>/api/compute/cli/callback` as a redirect of the Discord app.

## Sessions

A session is a time when a pod must run, such as a workshop. The `godfather.schedule` job runs every 5 minutes. It starts a pod 10 minutes before a session starts, and stops it when the session ends, unless a different session on the pod is still open. A pod that was already running when its session started is also stopped after it. The job does not touch pods with no sessions. A stopped pod costs only its disk, so one pod can serve a series of workshops.

| Route | Does |
| --- | --- |
| `GET .../pods/<pod_id>/sessions` | All sessions of the pod |
| `POST .../pods/<pod_id>/sessions` | `{"title", "start_at", "stop_at"}`, ISO 8601 with a time zone, 24 hours or less. 201 |
| `DELETE .../pods/<pod_id>/sessions/<id>` | Removes a session. If the pod started for it, the next run stops it |

## File manager

These officer routes work on the files of a running pod over SFTP, as root with the org's `backend` key. Paths are absolute. `...` is `/api/compute/<org>`.

| Route | Body | Does |
| --- | --- | --- |
| `GET .../pods/<pod_id>/files?path=/workspace` | | Folder entries, folders first |
| `POST .../files/read` | `{"path"}` | Text content, up to 1 MB |
| `POST .../files/write` | `{"path", "content"}` | Replaces a file with text, up to 1 MB |
| `POST .../files/download` | `{"path"}` | The file as an attachment, up to 100 MB |
| `POST .../files/upload` | multipart `file`, form `path` (folder) | Saves a file, up to 100 MB |
| `POST .../files/mkdir` | `{"path"}` | Makes a folder |
| `POST .../files/rename` | `{"old_path", "new_path"}` | Moves or renames |
| `POST .../files/delete` | `{"path"}` | Deletes a file, or a folder and its contents. Refuses `/`, `/workspace`, `/root` and `/home` |

A stopped pod returns 409. A failed SSH connection returns 502. Platform does not check pod host keys, because RunPod does not publish them.

Officers manage pods on the dashboard Godfather page, `/<org>/godfather`. From it they create, start, stop, restart and terminate pods, change who can connect, add and remove sessions, and work with the files of a running pod.

## Adding a hosting provider

A hosting provider is the cloud that Godfather pods and apps run on. `core/hosting.py` has the interface and the registry. The providers are RunPod (`core/integrations/runpod.py`) and This server (`core/integrations/server.py`); Godfather refuses a provider whose `godfather` is false. `GET /api/dashboard/<org>/hosting/providers` lists the providers with `configured` for the org, and the dashboard shows them in its Provider selects.

1. Write a client with the `HostingClient` calls: `list_pods`, `get_pod`, `create_pod`, `update_pod`, `start_pod`, `stop_pod` and `delete_pod`. Raise a `HostingError` subclass with the provider's HTTP status when a call fails. A missing pod gives `None` from `get_pod`.
2. Write a provider class with `name`, `title` and `integration`, and the methods `configured`, `client`, `status`, `machine`, `ssh_address` and `proxy_url`. `status` returns `RUNNING` for a running pod and `GONE` for `None`.
3. Register an integration for the provider's keys in `core/integrations/registry.py`, so officers connect it on Integrations.
4. Call `hosting.register()` in the module, and add the module to `PROVIDER_MODULES` in `core/hosting.py`.
5. The create bodies of Godfather pods (`pod_request` in `modules/godfather/service.py`) and of app manifests follow the RunPod v2 API. Map them to the new provider's API in its client, or give the provider its own request builder.
6. Show the provider's own fields in `dashboard/src/pages/godfather/new-pod.tsx` when it is selected, as the RunPod hardware fields are.

The `provider` column of `compute_pods` and `runpod_apps` keeps the name, so a rename breaks existing rows. The module name `runpod` stays, and the tables of `godfather` keep their `compute_` names. A later change can rename `modules/runpod` to `modules/hosting`.

## Limits

- Members have no web page to connect. They use the Godfather CLI or the routes above.
- The RunPod field names follow RunPod's REST API and are tested against a fake. Check them with a real key before you use the module in production.
