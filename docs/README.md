# Platform documentation

Platform is shared infrastructure for student orgs. One deployment serves many orgs. Each org is a Discord server and turns on only the modules it uses.

## Pages

| Page | Read it to |
| --- | --- |
| [Getting started](./getting-started.md) | Run Platform on your machine or on one RunPod pod |
| [Architecture](./architecture.md) | Learn the processes, the module pattern, jobs, tools and the MCP server |
| [Data model](./data-model.md) | Find a table and the module that owns it, and write a migration |
| [Authentication](./authentication.md) | Learn the sign-in types, tokens, decorators and access checks |
| [Integrations](./integrations.md) | Connect Notion, Google, GitHub, RunPod; add an integration |
| [API contract](./api-contract.md) | Change a route that a live client uses |
| [Writing a module](./writing-a-module.md) | Add a module and register it |
| [Operations](./operations.md) | Deploy, roll back, move to Postgres, turn off routes |
| [Frontends](./frontends.md) | Work on the dashboard and the member store (`dashboard/`) |
| [Alerts](./webhooks.md) | Send org events and feeds to Discord destinations; add an event |
| [Limits](./limits.md) | Read and change what each org may use; add a limit to a module |
| [Roadmap](./roadmap.md) | See what is left to build and the known issues |

## Module pages

Each module has a `README.md` in its folder with its files, routes, jobs, tools and tables. The modules below also have a page here, because they need setup or have a large surface.

| Page | Module |
| --- | --- |
| [Accounts](./modules/accounts.md) | Canvas, Google and Outlook sign-in for a member |
| [Agents](./modules/agents.md) | Conversations, memories, profile graph and turns for agents |
| [Calendar](./modules/calendar.md) | Notion events synced to Google Calendar |
| [Discord bot](./modules/discord-bot.md) | The bot process, its setup and its commands |
| [Feeds](./modules/feeds.md) | Job listings and hackathons posted to Discord channels |
| [Godfather](./modules/godfather.md) | RunPod pods, SSH certificates, file manager, sessions |
| [Knowledge](./modules/knowledge.md) | Sources, crawls and hybrid search |
| [LeetCode](./modules/leetcode.md) | Daily question post, solve checks and slash commands |
| [Points](./modules/points.md) | Members, points from events and the leaderboard |
| [Hosting apps](./modules/runpod-apps.md) | App manifests, deploys to RunPod or This server, health checks and rollback |
| [Store](./modules/storefront.md) | Merch store paid with points |
| [Shared content](./modules/submodules.md) | Content made once for every org (code name: submodules): campus pages and live queries for knowledge, such as the ASU submodule, and feeds for the Feeds module |
| [Uptime](./modules/uptime.md) | Checks of sites and Hosting apps, with events when one goes down or up |

## Notes

- `tests/contract/routes.txt` lists every route, its methods and its view. A test fails if the file and the app do not agree.
- An org is a row in `organizations`. It maps to one Discord server (guild).
- `org_prefix` is the URL name of an org, for example `robotics`. Most routes have it in the path.
- When a page and the code do not agree, the code is correct. Change the page in the same commit.
