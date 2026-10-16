# asu

The Arizona State University submodule. It adds public ASU pages to an org's knowledge as crawled sources, and answers live queries against ASU pages and APIs. With an officer's ASU sign-in, agents also search clubs and events on Sun Devil Central. Other pages that need an ASU sign-in (MyASU, Canvas) are not included.

## Files

| File | Holds |
| --- | --- |
| `__init__.py` | `SUBMODULE`: the pages and the live queries |
| `sources/` | Crawled ASU pages: one file for each source with its extractor, and the page list in `pages.py` |
| `queries/` | One file for each live query |
| `params.py` | ASU term codes, and dates and times in Arizona time |
| `signin/` | The ASU sign-in and the `asu.clubs` and `asu.events` tools. See [ASU sign-in](#asu-sign-in) |

## Pages

Sync adds each page as a crawled source with a key that starts with `asu/`. Some pages have their own extractor (library hours, events, courses, dining, scholarships, news, shuttles, jobs, sports). An extractor keeps each record on one line, so a chunk never splits a name from its hours or date. The `extractor` column of the source names it (`asu.<key>`).

## Live queries

Run them with `POST /api/submodules/asu/query` or the `submodules.query` tool with `submodule` set to `asu`. The old routes `/api/asu/queries`, `/api/asu/query` and `/api/asu/sync` give the same answers.

| Source | Parameters (required are marked) |
| --- | --- |
| courses | term (required), keywords, level, days, session, open_only |
| course_catalog | keywords (required), term |
| scholarships | keywords, citizenship, applicant, focus |
| events, news | keywords |
| library_catalog | keywords (required), type |
| library_hours, jobs | none |
| study_rooms | library (required), date (required) |
| sports | sport (required) |
| sports_news | sport, keywords |
| shuttles | route |
| campus_map | place (required) |
| social_media | account, keywords |
| dining | campus (required) |
| web | query (required), time_range. Needs a SearXNG server |

Pages that render with JavaScript (class search, events) need Firecrawl. The `web` query needs SearXNG. See [docs/modules/submodules.md](../../docs/modules/submodules.md).

## ASU sign-in

An officer of an org that subscribes to ASU signs in on the ASU card of the Shared tab of the dashboard Explore page with a NetID, a password and Duo. Platform keeps only the browser cookies, as the org secret `asu_session`. Agents with the `asu:read` scope then get two read-only tools:

| Tool | Parameters | Reads |
| --- | --- | --- |
| `asu.clubs` | keywords (required) | The Sun Devil Central club directory |
| `asu.events` | keywords | The Sun Devil Central events and the public ASU events calendar |

| File | Holds |
| --- | --- |
| `signin/browser.py` | The `Browser` interface and `Chromium`, which runs headless Chromium through Playwright |
| `signin/sso.py` | The sign-in on a page: the ASU form, Duo and its code, the Sun Devil Central sign-in link, and the check for a sign-in page |
| `signin/sundevil_central.py` | The club and event URLs and extractors |
| `signin/service.py` | Sign-in attempts, the saved session, page loads with it, and the `asu.session_expired` event |
| `signin/tools.py` | The `asu:read` scope and the two tools |

Playwright is an optional extra: `uv sync --extra browser`. The API image has it. With `BROWSER_URL` set, the sign-in uses the shared browser ([operations](../../docs/operations.md#run-the-shared-browser)); else run `uv run playwright install --with-deps chromium` on the machine. Without the package, the card says so and the tools do not show. The results are never added to knowledge. See [docs/integrations.md](../../docs/integrations.md#sign-in-to-asu).
