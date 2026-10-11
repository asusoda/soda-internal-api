"""Command-line tools: `flask --app main <group> <command>`.

org create     create an organization with the modules of a new org, optionally with more turned on or off
org list       list organizations and their module switches
org modules    turn modules on or off for an organization
jobs list      list registered jobs
jobs run       run a job now, in this process
config check   check settings, the database and migrations before a deploy
"""

import os

import click
from flask import Flask
from flask.cli import AppGroup

from core.config import config
from core.db import db_connect

org_cli = AppGroup("org", help="Organizations.")
jobs_cli = AppGroup("jobs", help="Background jobs.")
config_cli = AppGroup("config", help="Configuration.")


def _csv(value: str | None) -> tuple[str, ...]:
    return tuple(part.strip() for part in (value or "").split(",") if part.strip())


@org_cli.command("create")
@click.option("--name", required=True)
@click.option("--prefix", required=True, help="URL prefix, e.g. acm")
@click.option("--guild-id", required=True, help="Discord server id")
@click.option("--officer-role-id", default=None, help="Discord role id that marks officers")
@click.option("--description", default=None)
@click.option("--on", "modules_on", default="", help="Optional modules to turn on, comma-separated")
@click.option("--off", "modules_off", default="", help="Optional modules to turn off, comma-separated")
def org_create(name, prefix, guild_id, officer_role_id, description, modules_on, modules_off):
    """Create an organization. Optional modules start off, except those in NEW_ORG_MODULES."""
    from modules.organizations import service

    db = db_connect.SessionLocal()
    try:
        org = service.create_organization(
            db,
            name=name,
            prefix=prefix,
            guild_id=guild_id,
            officer_role_id=officer_role_id,
            description=description,
            modules_on=_csv(modules_on),
            modules_off=_csv(modules_off),
        )
        click.echo(f"Created {org.name} (id {org.id}, prefix {org.prefix})")
        _print_modules(org)
    except service.OrganizationError as e:
        raise click.ClickException(str(e)) from e
    finally:
        db.close()


def _print_modules(org) -> None:
    from modules.organizations import service

    states = ", ".join(f"{m['name']}={'on' if m['enabled'] else 'off'}" for m in service.module_states(org))
    click.echo(f"  modules: {states}")


@org_cli.command("list")
def org_list():
    """List organizations."""
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        for org in db.query(Organization).order_by(Organization.id).all():
            status = "active" if org.is_active else "inactive"
            click.echo(f"{org.id}\t{org.prefix}\t{org.name}\tguild {org.guild_id}\t{status}")
            _print_modules(org)
    finally:
        db.close()


@org_cli.command("modules")
@click.argument("prefix")
@click.option("--on", "modules_on", default="", help="Modules to turn on, comma-separated")
@click.option("--off", "modules_off", default="", help="Modules to turn off, comma-separated")
def org_modules(prefix, modules_on, modules_off):
    """Show or change an organization's module switches."""
    from modules.organizations import service

    db = db_connect.SessionLocal()
    try:
        org = service.find_by_prefix(db, prefix)
        if org is None:
            raise click.ClickException(f"No organization with prefix {prefix}")
        changes = dict.fromkeys(_csv(modules_on), True) | dict.fromkeys(_csv(modules_off), False)
        if changes:
            try:
                service.set_modules(db, org, changes)
            except service.ModuleError as e:
                raise click.ClickException(str(e)) from e
        _print_modules(org)
    finally:
        db.close()


@jobs_cli.command("list")
def jobs_list():
    """List registered jobs."""
    from core import jobs

    click.echo(f"backend: {jobs.queue_backend()}")
    for name, entry in sorted(jobs.JOBS.items()):
        click.echo(f"{name}\t{entry.cron or 'on demand'}\tretry={entry.retry}")


@jobs_cli.command("run")
@click.argument("name")
@click.option("--arg", "-a", "args", multiple=True, help="key=value, repeatable")
def jobs_run(name, args):
    """Run a job now, in this process (not through the queue)."""
    from core import jobs

    entry = jobs.JOBS.get(name)
    if entry is None:
        raise click.ClickException(f"No job named {name}. See `jobs list`.")
    kwargs = {}
    for pair in args:
        key, sep, value = pair.partition("=")
        if not sep:
            raise click.ClickException(f"--arg must be key=value, got {pair}")
        kwargs[key] = int(value) if value.lstrip("-").isdigit() else value
    try:
        jobs._execute(entry, kwargs)
    except Exception as e:
        raise click.ClickException(f"{name} failed: {e}") from e
    click.echo(f"{name} finished")


@config_cli.command("check")
def config_check():
    """Check settings, the database and migrations. Exits non-zero on a failure."""
    failures = 0

    def report(level: str, message: str) -> None:
        nonlocal failures
        if level == "FAIL":
            failures += 1
        click.echo(f"{level:4}  {message}")

    for var in ("BOT_TOKEN", "CLIENT_ID", "CLIENT_SECRET", "SYS_ADMIN"):
        report("ok" if os.environ.get(var) else "FAIL", f"{var} {'set' if os.environ.get(var) else 'missing'}")
    _check_discord(report)
    if not (os.environ.get("FLASK_SECRET_KEY") or os.environ.get("SECRET_KEY")):
        report("WARN", "FLASK_SECRET_KEY missing: sessions end on every restart")
    for var, feature in (
        ("CLERK_SECRET_KEY", "member store login"),
        ("NOTION_API_KEY", "calendar (unless every org saves its own token)"),
        ("SENTRY_DSN", "error reporting"),
    ):
        if not os.environ.get(var):
            report("WARN", f"{var} missing: {feature} off")
    if not os.path.exists("google-secret.json"):
        report("WARN", "google-secret.json missing: Google Calendar off")

    from core import secrets

    try:
        report(
            "ok" if secrets.configured() else "WARN", f"SECRETS_KEY {'valid' if secrets.configured() else 'missing'}"
        )
    except ValueError as e:
        report("FAIL", f"SECRETS_KEY invalid: {e}")

    if not getattr(config, "ACCESS_ENFORCE", False):
        report("WARN", "ACCESS_ENFORCE is off: access checks only log")

    _check_database(report)
    if failures:
        raise click.ClickException(f"{failures} check(s) failed")
    click.echo("All required checks passed")


def _check_discord(report) -> None:
    """Name the Discord app of BOT_TOKEN, and fail when CLIENT_ID is from another app."""
    from core.integrations.discord import DiscordDirectory, DiscordUnavailable

    if not config.BOT_TOKEN:
        return
    try:
        who = DiscordDirectory(config.BOT_TOKEN).identity()
    except DiscordUnavailable as e:
        report("FAIL", f"BOT_TOKEN refused by Discord: {e}")
        return
    report("ok", f"Discord bot {who['bot_name']} of app {who['app_name']} ({who['app_id']})")
    client_id = os.environ.get("CLIENT_ID")
    if client_id and client_id != who["app_id"]:
        report("FAIL", f"CLIENT_ID {client_id} is from another Discord app than BOT_TOKEN ({who['app_id']})")


def _check_database(report) -> None:
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    from core import jobs

    try:
        with db_connect.engine.connect() as conn:
            current = MigrationContext.configure(conn).get_current_revision()
    except Exception as e:
        report("FAIL", f"database unreachable: {e}")
        return
    report("ok", f"database reachable ({db_connect.engine.dialect.name})")
    head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
    if current == head:
        report("ok", f"migrations at head ({head})")
    else:
        report("FAIL", f"migrations at {current}, head is {head}: run `alembic upgrade head`")
    report("ok", f"job backend: {jobs.queue_backend()}")


def register_cli(app: Flask) -> None:
    for group in (org_cli, jobs_cli, config_cli):
        app.cli.add_command(group)
