# feeds

Posts new job listings and hackathons to Discord webhooks: each feed reads one source on a schedule and posts only new items to a Discord webhook. A feed has a kind: `github_jobs` (the job table of a GitHub README) or `hackathons` (Hack Club, Euro-Hackathons and Hackalist). When the org has the module off, its feeds are hidden and do not run. The presets come from the submodules the org subscribes to, such as `careers`. Other org events go through `core/webhooks.py`.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Officer routes to create, list, update, delete and run feeds |
| `tools.py` | The `feeds.*` tools for agents |
| `service.py` | Feeds, runs, duplicate checks and Discord webhook posts |
| `types.py` | `Item`, `SourceError` and the fetch signature of a source |
| `github_jobs.py` | The `github_jobs` kind: reads the job table, config checks and the fetch |
| `hackathons.py` | The `hackathons` kind: reads the hackathon listings, config checks and the fetch |
| `models.py` | Feeds, the items each feed posted, and its runs |
| `jobs.py` | The scheduled run and the run on request |

## Surface

- Routes: `/api/feeds/<org>/feeds` and `/api/feeds/<org>/presets`. Officers of the org only. `GET /feeds/<key>/history` returns the runs and items of a feed. `GET /presets` returns the feeds that the org's subscribed submodules offer.
- Jobs: `feeds.run_due`, schedule `*/15 * * * *`; `feeds.run_feed`, started by the run route.
- Tools: `feeds.list`, `feeds.presets`, `feeds.history`, `feeds.save`, `feeds.run`, `feeds.delete` (confirm), all with scope `feeds:manage`. Tools marked confirm run only with `confirm=true`.
- Tables: `alert_feeds`, `alert_posts`, `alert_runs`. Secrets: `alert_webhook_<feed key>`.
- Switch: `feeds`. Migration `a3c5e7f9b1d3` made it from the `job_webhook` and `hackathon_webhook` switches: on when either was on.

See [docs/modules/feeds.md](../../docs/modules/feeds.md).
