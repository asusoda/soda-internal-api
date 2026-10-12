# games

Runs Jeopardy games in an org's Discord server. Officers upload games, select the active one and run it with the bot commands. `GameCog` makes the team roles and channels, posts questions and keeps the scoreboard.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Game controls: upload, list, set and start the active game, show questions and answers, give team points |
| `service.py` | The game JSON check, the stored games (`list_games`, `get_game`, `save_game`), and reads of a game file from `./data` |
| `cog.py` | `GameCog`: game channels and roles, sign-up, questions, scoreboard |
| `ui.py` | Discord views for question posts |
| `jeopardy/` | `JeopardyGame`, `JeopardyQuestion`, `Team` |
| `models.py` | Stored games and the active game |

## Surface

- Routes: `/api/bot`. Each route needs an officer of an org that has the `games` switch on. For another officer, each route returns 404. The superadmin always passes. The routes that run a game need the bot in the API process (`current_app.auth_bot`), so they fail under gunicorn.
- Jobs: none.
- Tools: none.
- Tables: `jeopardy_game`, `active_game`. One game runs at a time for the deployment, in the first server of the bot.

## Known gaps

- The logic that runs a game is in `api.py` and `cog.py`, not in `service.py`. The routes need the bot in the API process, so the AIS deployment turns them off with `DISABLED_ROUTES`.
- Game state is in memory and is for the whole deployment, not for one org.
