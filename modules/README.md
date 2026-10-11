# Modules

One folder for each module. Each folder has a `README.md` with its files and its surface: routes, jobs, tools and tables. [docs/writing-a-module.md](../docs/writing-a-module.md) gives the rules and the places to register a new module.

The folders are not nested. `CATEGORIES` in `manifest.py` groups the modules below in the same sections as the Explore page of the dashboard. Each module is in one category, and a module can have submodules: content in `submodules/` that the module reads. `CATALOG` in `manifest.py` gives the title, description, needs and submodules that the page shows for each module. A new org starts with every module in the Org switch column off.

## Core

Core modules are always on. The Explore page of the dashboard does not show them.

| Module | Does | Org switch |
| --- | --- | --- |
| [alerts](alerts/README.md) | The org's events, such as a failed job, sent to its destinations (Discord webhooks). Feeds post to a destination too | |
| [auth](auth/README.md) | Discord sign-in, tokens, access checks, machine tokens and scopes | |
| [bot](bot/README.md) | The Discord bot and its helper cog | |
| [dashboard](dashboard/README.md) | Overview, branding, CI runs and the module catalog for the officer dashboard | |
| [mcp](mcp/README.md) | The MCP server and `/api/tools`. A token's scopes decide what an agent can call | |
| [organizations](organizations/README.md) | Orgs, config, module switches, secrets and machine tokens | |
| [public](public/README.md) | Open reads | |
| [submodules](submodules/README.md) | Loads the submodules in `submodules/`. Explore shows each submodule under the module that reads it | |
| [superadmin](superadmin/README.md) | Orgs for the whole deployment | |
| [users](users/README.md) | Members and memberships | |

## Storage

| Module | Does | Org switch |
| --- | --- | --- |
| [knowledge](knowledge/README.md) | Sources, crawls and hybrid search | `knowledge` |
| [points](points/README.md) | Points, leaderboards and CSV imports | `points` |
| [storefront](storefront/README.md) | Merch store paid in points | `storefront` |
| [accounts](accounts/README.md) | Canvas, Google and Outlook sign-in for a member | `accounts` |

## AI and agents

| Module | Does | Org switch |
| --- | --- | --- |
| [agents](agents/README.md) | Conversations, memories, profile graph and pending actions for agents | `agents` |
| [integrations](integrations/README.md) | Tools of connected services (GitHub) passed through to their MCP servers | `integrations` |

## Webhooks

| Module | Does | Org switch |
| --- | --- | --- |
| [feeds](feeds/README.md) | New job listings and hackathons posted to an alert destination | `feeds` |

## Automations

| Module | Does | Org switch |
| --- | --- | --- |
| [calendar](calendar/README.md) | Notion events synced to Google Calendar | `calendar` |
| [uptime](uptime/README.md) | Checks of sites and Hosting apps, with events when one goes down or up | `uptime` |

## Bots

| Module | Does | Org switch |
| --- | --- | --- |
| [leetcode](leetcode/README.md) | The daily LeetCode post and solve checks | `leetcode` |
| [games](games/README.md) | Jeopardy in Discord | `games` |

## Compute

| Module | Does | Org switch |
| --- | --- | --- |
| [godfather](godfather/README.md) | Pods on a hosting provider (RunPod) that members connect to with the Godfather CLI | `godfather` |
| [runpod](runpod/README.md) | App deploys to a hosting provider (RunPod). The dashboard calls it Hosting | `runpod` |

## Shared files

`registry.py` mounts each blueprint. `manifest.py` lists the categories and the model, job and tool modules. `cli.py` has the `flask --app main org`, `jobs` and `config` commands. `tests/test_module_layout.py` checks that each module is in these lists and in the docs.

The modules from SoDA (points, storefront, users, superadmin, calendar, organizations, public, auth, games) do not follow the module pattern in full. Each README lists its Known gaps.
