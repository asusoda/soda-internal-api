# points

Keeps the points that an org's members earn. Officers add members, give points by hand or from an event attendance CSV, and read the leaderboard. Members sign in with Clerk to see their profile.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Member and points routes, CSV upload, leaderboard, member sign-in and profile |
| `service.py` | The leaderboards, point totals, the member list with points, and the award, list and delete of entries; declares `points:read` and `points:write` |
| `csv_import.py` | The attendance CSV import that the `points.import_event_csv` job runs |
| `models.py`, `tools.py`, `jobs.py` | Point entries; the `points.*` tools; the CSV import job |

## Surface

- Routes: `/api/points`, behind the `points` switch. Most routes need an officer of the org. `DELETE /<org_prefix>/entries/<id>` deletes one entry by its id; `DELETE /<org_prefix>/delete_points` deletes a member's first entry for an event. `/<org_prefix>/leaderboard` is open and shows emails only to a signed-in caller. `/member_login` needs a Clerk token, and `/member_profile` reads the session it sets.
- Jobs: `points.import_event_csv`, started by the CSV upload.
- Tools: `points.leaderboard` (scope `points:read`); `points.entries`, `points.history` (scope `members:read`); `points.award`, `points.import_csv`, `points.delete` (confirm) (scope `points:write`). A member is an email, uuid, username or Discord id. `points.award` gives points to up to 100 members in one commit.
- Tables: `points`. Members and memberships are in `modules/users`.
- Cache: `/<org_prefix>/users` and `/<org_prefix>/get_points` are kept for 30 seconds and the leaderboard for 300 seconds, with an ETag (`core/http/cached.py`). A successful write to the API, or the end of a CSV import, drops them. A write from the bot or the MCP server shows after the time runs out.

## Known gaps

- Views in `api.py` open their own session and query. The leaderboards, the member list, point adds and the event and entry deletes are in `service.py`. Move the rest one route at a time, with the contract tests.
- The camelCase routes (`getUserPoints`, `getUserTotalPoints`) are aliases. See Cleanup in `docs/roadmap.md`.
