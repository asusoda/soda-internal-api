# App templates

Ready-made apps that officers create from the Templates dialog of the Hosting page. Each folder holds a `platform.app.yaml` and a `README.md`. A template adds no code to Platform.

| Template | App |
| --- | --- |
| [vaultwarden](vaultwarden/README.md) | Password manager for the org |

## Write a template

1. Make a folder `apps/<name>/`. The name is lowercase letters, digits and dashes.
2. Write `platform.app.yaml`: a [manifest](../docs/modules/runpod-apps.md#manifest) and a `template` block. Use images from GHCR, not Docker Hub.

   ```yaml
   template:
     title: Example
     summary: One line about the app.
     tag: "1.0.0"
     inputs:
       - {kind: secret, key: API_TOKEN, label: API token}
       - {kind: env, key: DOMAIN, label: Public URL, required: false}
   ```

3. Write a `README.md` with the inputs and what the officer must know before use.

| Input kind | Sets |
| --- | --- |
| `image` | `image`. Leave `image` out of the manifest |
| `env` | `env[key]` |
| `secret` | `secret_env[key]`, as the org secret `app_<app>_<key in lower case>` |
| `volume` | `volumeId` of each entry in `mounts.network` |
| `data_center` | `dataCenterIds` |

Inputs are required unless `required: false`. `tag` is optional; the dashboard puts it in the deploy form. `tests/contract/test_app_templates.py` loads each template.
