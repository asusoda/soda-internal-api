# Sub-modules

A sub-module is content for one campus or topic that a module reads and any org can use: public pages crawled into knowledge, live queries that agents run, feeds for the webhook modules, and the school's Canvas URL. A sub-module holds content and settings, not new behavior. It adds no tables, routes or dashboard pages. Use a [module](../docs/writing-a-module.md) for a feature.

| Sub-module | Content |
| --- | --- |
| [asu](asu/README.md) | Arizona State University: library hours, events, courses, dining, scholarships, news, shuttles, jobs, sports; the ASU Canvas URL; the ASU sign-in for Sun Devil Central |
| [careers](careers/__init__.py) | Feeds for software internships, new grad roles and hackathons (`feeds`) |

## Write a sub-module

1. Make a folder `submodules/<name>/`. The name is lowercase letters, digits and underscores. The sub-module owns the org's knowledge sources with keys that start with `<name>/`.
2. In `submodules/<name>/__init__.py`, set `SUBMODULE`:

   ```python
   from modules.submodules.types import QueryParam, QuerySource, Source, Submodule

   SUBMODULE = Submodule(
       name="example",
       title="Example University",
       description="Public pages of Example University: library hours and events.",
       sources=(
           Source(key="library_hours", url="https://lib.example.edu/hours", category="library", fetch_every_hours=24),
       ),
       queries=(
           QuerySource(
               key="events",
               description="Campus events that match keywords.",
               params=(QueryParam("keywords", "Words to search for."),),
               to_url=lambda p: "https://events.example.edu/search?q=" + p.get("keywords", ""),
           ),
       ),
   )
   ```

3. Optional parts of a `Submodule`:
   - `feeds`: feeds that officers pick under **New feed** > **Start from** on the Job alerts and Hackathons pages of the Feeds module. Each `Feed` has a key (lowercase letters, digits and dashes), a title, a description, and the `kind` and `config` that the [feeds module](../docs/modules/feeds.md) takes. The `kind` is `github_jobs` or `hackathons`.
   - `canvas_url`: the school's Canvas, like `https://canvas.example.edu`. Member sign-in to Canvas uses it when `ACCOUNTS_CANVAS_URL` is not set and only one sub-module sets it.
4. Optional: give a `Source` or `QuerySource` an `extractor` that turns the fetched page into one line for each record. Helpers are in `modules/submodules/text.py`. A query that calls an API sets `answer` instead of `to_url`. Add `modules.submodules.web.QUERY` to `queries` for web search.
5. Add a `README.md` that lists the pages and the queries, and add the sub-module to the table above.
6. Add tests in `tests/contract/` with saved pages in a fixtures folder. Do not fetch live pages in tests.

Rules:

- Public pages only. Do not add pages that need a sign-in. The ASU sign-in in `asu/signin/` is the one exception: it has its own tools, routes in the dashboard module and an org secret, and its results are never indexed.
- A sub-module imports only `modules.submodules` and the standard library. It does not import Flask. `asu/signin/` also imports `core` and `modules.auth.scopes`.
- Do not change a source key after orgs use it. A new key makes a new source, and the old one is turned off on the next sync.

Platform loads every folder in `submodules/` on start. Officers add a sub-module's pages on the Knowledge card of the Explore page, and its feeds on the page of each webhook module.
