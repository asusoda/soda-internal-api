# mcp

Serves the tools of other modules to apps and agents with a machine token: over MCP streamable HTTP at `/mcp`, and over HTTP at `/api/tools`. The module is Core and always on. A caller sees only the tools that its token scopes and its org's module switches allow. The Tokens page of the dashboard shows how to connect.

## Files

| File | Holds |
| --- | --- |
| `server.py` | The MCP server app (`build_app`), run by `mcp_main.py` |
| `runtime.py` | Lists and calls tools for a machine caller: scope, module switch and input checks; writes each call to the audit log; runs the `batch` tool |
| `api.py` | `GET /api/tools` lists tools; `POST /api/tools/<name>` calls one |

## Surface

- Routes: `/api/tools`. Machine token required.
- Jobs: none.
- Tools: `batch`, which runs 1 to 25 calls of other tools in order. Each call has its own scope check, module switch, confirm step and audit entry. A token sees `batch` when it can call one or more other tools. The other tools are `core.tools.TOOLS`, which the modules in `TOOL_MODULES` in `modules/manifest.py` fill.
- Tables: none.
- Limits: `mcp.calls_per_minute` (`runtime.py`). Each tool call, also each call in a batch, counts. Over the limit the call returns 429. See [docs/limits.md](../../docs/limits.md).

See [docs/architecture.md](../../docs/architecture.md#tools-and-the-mcp-server).
