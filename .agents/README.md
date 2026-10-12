# Agent files

Instructions and skills for AI coding agents working in this repository. `AGENTS.md` (also
`CLAUDE.md`) at the repo root describes the codebase; this folder holds the procedures.

`.claude/skills` is a link to `.agents/skills`, so Claude Code loads the same skills. Other agents
read the `SKILL.md` files directly.

`setup` prepares a new Amp orb. It installs the Node version in `.nvmrc`, Python 3.12, the uv
environment and the npm dependencies of `dashboard/` and `site/`.

## Skills

| Skill | Use it to | Origin |
| --- | --- | --- |
| `check` | Run the gate: `make ci`, bandit, the site build | this repo |
| `new-module` | Add a module and register it everywhere | this repo |
| `migration` | Create and test an Alembic migration | this repo |
| `api-contract` | Change a route a live client depends on | this repo |
| `pr-ready` | Prepare a branch and keep its PR green | this repo |
| `technical-writing` | Write docs, comments and messages in Simplified Technical English | this repo, after ASD-STE100 |
| `test-driven-development` | Write the failing test first | [obra/superpowers](https://github.com/obra/superpowers), MIT |
| `systematic-debugging` | Find the root cause before fixing | [obra/superpowers](https://github.com/obra/superpowers), MIT |
| `verification-before-completion` | Run the command and read its output before saying done | [obra/superpowers](https://github.com/obra/superpowers), MIT |
| `postgres-strict` | Schema, index and migration safety on Postgres | [0xMassi/claude-skills](https://github.com/0xMassi/claude-skills), MIT |
| `security-audit-standard` | Audit before a release | [0xMassi/claude-skills](https://github.com/0xMassi/claude-skills), MIT |

Third-party skills are copied with their LICENSE files. Update them by copying again from the
source, not by editing in place.
