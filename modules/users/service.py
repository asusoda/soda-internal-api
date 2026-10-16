"""Member lookup, upsert and the member field helpers. No Flask here."""

import functools
import uuid
from collections.abc import Mapping
from typing import Any, cast

from sqlalchemy.exc import IntegrityError

from core import webhooks
from core.config import config
from core.db import db_connect
from core.errors import ServiceError
from core.integrations.discord import DiscordDirectory, DiscordUnavailable
from core.log import get_logger
from modules.auth import scopes
from modules.users.models import User, UserOrganizationMembership

logger = get_logger(__name__)

scopes.declare("members:read", "Read the org's members with emails, student IDs, profile fields and points history")
scopes.declare("members:write", "Add and change the org's members, and add the members of its Discord server")


class MemberError(ServiceError):
    pass


webhooks.declare(
    "member.joined",
    "New members",
    "A person joins the org at sign-in, through a form or a CSV import. A Discord member sync does not send it.",
)

# Request and response keys kept for thesoda.io and the dashboard, and the column each one names
LEGACY_MEMBER_KEYS = {"asu_id": "student_id", "academic_standing": "class_standing"}

UNIQUE_USER_FIELDS = ("username", "email", "discord_id", "student_id")


def member_input(data: Mapping[str, Any]) -> dict[str, Any]:
    """Request fields with each legacy key renamed to its column. A column name sent as well wins."""
    fields = {key: value for key, value in data.items() if key not in LEGACY_MEMBER_KEYS}
    for legacy, column in LEGACY_MEMBER_KEYS.items():
        if legacy in data and column not in data:
            fields[column] = data[legacy]
    return fields


def legacy_member_fields(user: User) -> dict[str, Any]:
    """The student id and class standing under their legacy response keys."""
    return {legacy: getattr(user, column) for legacy, column in LEGACY_MEMBER_KEYS.items()}


def member_fields(user: User, membership: UserOrganizationMembership | None = None) -> dict[str, Any]:
    """The student id and class standing under both key sets, and the org's profile fields when a membership is given."""
    fields = legacy_member_fields(user)
    fields.update({column: getattr(user, column) for column in LEGACY_MEMBER_KEYS.values()})
    if membership is not None:
        fields["profile_fields"] = dict(cast(dict[str, Any], membership.profile_fields or {}))
    return fields


def merge_profile_fields(membership: UserOrganizationMembership, changes: Any) -> str | None:
    """Merges changes into the membership's profile fields; a null value removes the key. Returns an error or None."""
    if not isinstance(changes, Mapping):
        return "profile_fields must be an object"
    merged = dict(cast(dict[str, Any], membership.profile_fields or {}))
    for key, value in changes.items():
        if not isinstance(key, str) or not key.strip():
            return "profile_fields keys must be non-empty strings"
        if value is None:
            merged.pop(key, None)
        elif isinstance(value, str | int | float | bool):
            merged[key] = value
        else:
            return f"profile_fields.{key} must be a string, number or boolean"
    membership.profile_fields = merged
    return None


def find_by_identifier(db, identifier) -> User | None:
    """The user whose email, else uuid, else username is identifier."""
    user = db.query(User).filter_by(email=identifier).first()
    if not user:
        user = db.query(User).filter_by(uuid=identifier).first()
    if not user:
        user = db.query(User).filter_by(username=identifier).first()
    return user


def active_members(db, organization_id) -> list[tuple[UserOrganizationMembership, User]]:
    """The org's active memberships with their users, in membership order. One query."""
    return (
        db.query(UserOrganizationMembership, User)
        .join(User, User.id == UserOrganizationMembership.user_id)
        .filter(UserOrganizationMembership.organization_id == organization_id, UserOrganizationMembership.is_active)
        .order_by(UserOrganizationMembership.id)
        .all()
    )


def active_membership(db, user_id, organization_id) -> UserOrganizationMembership | None:
    """The user's active membership in the org, or None."""
    return (
        db.query(UserOrganizationMembership)
        .filter_by(user_id=user_id, organization_id=organization_id, is_active=True)
        .first()
    )


def officer_may_edit(db, user_id, organization_id) -> bool:
    """Whether an officer of the org may change the user's own fields: the user is a member of this org only."""
    memberships = db.query(UserOrganizationMembership.organization_id).filter_by(user_id=user_id, is_active=True).all()
    return {row.organization_id for row in memberships} == {int(organization_id)}


def update_user_field(db, user, field_name, field_value, organization_id=None):
    """Set one user field and commit. A unique field must not belong to another user. Returns (ok, message)."""
    try:
        if not hasattr(user, field_name):
            return False, f"Invalid field: {field_name}"

        if field_name in UNIQUE_USER_FIELDS and field_value:
            existing = db.query(User).filter(getattr(User, field_name) == field_value).first()
            if existing and existing.id != user.id:
                return False, f"{field_name} is already taken"

        setattr(user, field_name, field_value)
        db.commit()

        return True, f"{field_name} updated successfully"

    except Exception as e:
        db.rollback()
        return False, str(e)


def member_dict(user: User, membership: UserOrganizationMembership | None = None) -> dict[str, Any]:
    """A member as the member tools return it."""
    return {
        "id": user.id,
        "uuid": user.uuid,
        "name": user.name,
        "username": user.username,
        "email": user.email,
        **member_fields(user, membership),
        "major": user.major,
        "discord_id": user.discord_id,
        "joined_at": membership.joined_at.isoformat() if membership is not None and membership.joined_at else None,
    }


def update_member(db, organization_id, user_identifier, data: Mapping[str, Any]) -> dict[str, Any]:
    """Update the fields sent for an active member. Legacy keys name their columns. Commits each field.

    Returns user, membership, updated_fields and errors. A field that fails is in errors; the others are saved.
    """
    user = find_by_identifier(db, user_identifier)
    if not user:
        raise MemberError("User not found", 404)
    membership = active_membership(db, user.id, organization_id)
    if not membership:
        raise MemberError("User is not a member of this organization", 400)
    updated_fields: list[str] = []
    errors: list[str] = []
    may_edit_user = officer_may_edit(db, user.id, organization_id)
    for field_name, field_value in data.items():
        if field_name == "user_identifier":
            continue
        column = LEGACY_MEMBER_KEYS.get(field_name, field_name)
        if column != field_name and column in data:
            continue  # the column name sent alongside wins
        if column != "profile_fields" and not may_edit_user:
            errors.append(f"{field_name}: the user is a member of another organization")
            continue
        if column == "profile_fields":
            error = merge_profile_fields(membership, field_value)
            if error:
                errors.append(f"{field_name}: {error}")
                continue
            db.commit()
            updated_fields.append(field_name)
            continue
        success, message = update_user_field(db, user, column, field_value, organization_id)
        if success:
            updated_fields.append(field_name)
        else:
            errors.append(f"{field_name}: {message}")
    return {"user": user, "membership": membership, "updated_fields": updated_fields, "errors": errors}


def _find_for_upsert(db, user_data, discord_id, user_identifier):
    """The existing user by identifier, then email, student id and Discord id, or None."""
    user = None
    if user_identifier:
        user = find_by_identifier(db, user_identifier)
    if not user and user_data.get("email"):
        user = db.query(User).filter_by(email=user_data["email"]).first()
    if not user and user_data.get("student_id") and user_data["student_id"] != "N/A":
        user = db.query(User).filter_by(student_id=user_data["student_id"]).first()
    if not user and discord_id:
        user = db.query(User).filter_by(discord_id=discord_id).first()
    return user


def _recover_duplicate_email(db, organization_id, email):
    """After a duplicate email error: the user with that email, made an active member of the org, or None."""
    try:
        existing_user = db.query(User).filter_by(email=email).first()
        if not existing_user:
            return None
        logger.warning(f"Duplicate email found for {email}, returning existing user.")

        membership = (
            db.query(UserOrganizationMembership)
            .filter_by(user_id=existing_user.id, organization_id=organization_id)
            .first()
        )
        if membership:
            if hasattr(membership, "is_active") and not membership.is_active:
                membership.is_active = True
                db.commit()
        else:
            db.add(UserOrganizationMembership(user_id=existing_user.id, organization_id=organization_id))
            db.commit()

        logger.info(f"Successfully recovered existing user {existing_user.id}")
        return existing_user
    except Exception as recovery_error:
        db.rollback()
        logger.error(f"Failed to recover from IntegrityError: {recovery_error}")
        return None


def _announce_join(organization_id, user: User) -> None:
    """Send the member.joined webhook event. The message has the name and username, not the email."""
    fields = (("Username", str(user.username or "-")),)
    message = webhooks.Message(title=f"{user.name or 'A new member'} joined", fields=fields, color=webhooks.GREEN)
    webhooks.emit(int(organization_id), "member.joined", message)


def manage_user_in_organization(
    db, organization_id, user_data, discord_id=None, user_identifier=None, by_officer=False
):
    """Find, update or create a user and make them a member of the org. Commits.

    With by_officer, an existing user's own fields and Discord id change only when officer_may_edit allows it.
    Returns (user or None, ok, message).
    """
    try:
        user_data = member_input(user_data)
        profile_changes = user_data.pop("profile_fields", None)
        user = _find_for_upsert(db, user_data, discord_id, user_identifier)

        if user:
            updated_fields = []
            if by_officer and not officer_may_edit(db, user.id, organization_id):
                user_data, discord_id = {}, None
            for field, value in user_data.items():
                if value is not None and hasattr(user, field):
                    current_value = getattr(user, field)
                    if current_value != value:
                        success, message = update_user_field(db, user, field, value, organization_id)
                        if success:
                            updated_fields.append(field)
                        else:
                            return user, False, message

            if discord_id and not user.discord_id:
                success, message = update_user_field(db, user, "discord_id", discord_id, organization_id)
                if success:
                    updated_fields.append("discord_id")

            membership = active_membership(db, user.id, organization_id)
            if not membership:
                membership = UserOrganizationMembership(user_id=user.id, organization_id=organization_id)
                db.add(membership)
                db.commit()
                updated_fields.append("organization_membership")
                _announce_join(organization_id, user)

            if profile_changes is not None:
                error = merge_profile_fields(membership, profile_changes)
                if error:
                    db.rollback()
                    return user, False, error
                db.commit()
                updated_fields.append("profile_fields")

            action = "updated" if updated_fields else "found"
            message = f"User {action}" + (f" ({', '.join(updated_fields)})" if updated_fields else "")
            return user, True, message

        student_id = user_data.get("student_id")
        new_user = User(
            discord_id=discord_id,
            username=user_data.get("username"),
            name=user_data.get("name", "Unknown"),
            email=user_data.get("email"),
            student_id=student_id if student_id and student_id != "N/A" else None,
            class_standing=user_data.get("class_standing", "N/A"),
            major=user_data.get("major", "N/A"),
            uuid=str(uuid.uuid4()),
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        membership = UserOrganizationMembership(user_id=new_user.id, organization_id=organization_id)
        if profile_changes is not None:
            error = merge_profile_fields(membership, profile_changes)
            if error:
                db.rollback()
                return new_user, False, error
        db.add(membership)
        db.commit()
        _announce_join(organization_id, new_user)

        return new_user, True, "User created successfully"

    except IntegrityError as e:
        db.rollback()

        if user_data.get("email"):
            existing_user = _recover_duplicate_email(db, organization_id, user_data.get("email"))
            if existing_user:
                return existing_user, True, "User already existed (recovered from duplicate email error)"

        logger.error(f"IntegrityError in manage_user_in_organization: {e}")
        return None, False, str(e)

    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error in manage_user_in_organization: {e}")
        return None, False, str(e)


def get_or_create_user(discord_id, organization_id, username=None):
    """The member with this Discord id, created and added to the org when missing. None on an error."""
    db = next(db_connect.get_db())
    try:
        user_data = {"username": username, "name": username or f"User_{discord_id}"}

        user, success, message = manage_user_in_organization(db, organization_id, user_data, discord_id=discord_id)

        if success:
            logger.debug(f"{message} - User {user.id} in org {organization_id}")
            return user
        logger.debug(f"Error: {message}")
        return None

    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return None
    finally:
        db.close()


def link_or_create_user(organization_id, user_data, discord_id=None, by_officer=False):
    """The member that user_data names (by student id, email or username), created when missing. None on an error."""
    db = next(db_connect.get_db())
    try:
        user, success, message = manage_user_in_organization(
            db, organization_id, user_data, discord_id=discord_id, by_officer=by_officer
        )

        if success:
            logger.debug(f"{message} - User {user.id if user else 'None'} for org {organization_id}")
            return user
        logger.debug(f"Error: {message}")
        return None

    except Exception as e:
        logger.error(f"Error linking/creating user: {e}")
        return None
    finally:
        db.close()


def _clerk_name(clerk_user, email: str) -> str:
    """The first and last name on the Clerk user, or the part of the email before the @."""
    raw_first = getattr(clerk_user, "first_name", None)
    raw_last = getattr(clerk_user, "last_name", None)
    first_name = str(raw_first).strip() if raw_first not in (None, "", "None") else ""
    last_name = str(raw_last).strip() if raw_last not in (None, "", "None") else ""
    name = f"{first_name} {last_name}".strip()
    if not name:
        name = email.split("@")[0]
        logger.debug(f"No name from Clerk, using email username: {name}")
    else:
        logger.debug(f"Extracted name from Clerk: {name}")
    return name


def get_or_create_user_from_clerk(db, organization_id, clerk_user, email):
    """The member with this Clerk email, created and added to the org when missing. None on an error."""
    if not clerk_user:
        logger.error("get_or_create_user_from_clerk called with no clerk_user")
        return None

    if not email or not isinstance(email, str) or "@" not in email:
        logger.error(f"get_or_create_user_from_clerk called with invalid email: {email!r}")
        return None

    user_data = {
        "email": email,
        "name": _clerk_name(clerk_user, email),
        "username": None,
        "discord_id": None,
        "student_id": None,
        "class_standing": "N/A",
        "major": "N/A",
    }

    user, success, message = manage_user_in_organization(db, organization_id, user_data, user_identifier=email)

    if success:
        logger.info(
            f"Clerk auth: {message} - User {user.id if user else 'None'} (name: {user.name if user else 'None'}) for org {organization_id}"
        )
        return user
    logger.error(f"Failed to create/get user from Clerk: {message}")
    return None


# Members from the org's Discord server

SYNC_CHUNK = 500
NO_DIRECTORY = "Discord is not set up on the API, so the server cannot be read."
NO_MEMBERS_INTENT = (
    "Discord refused the member list. Turn on Server Members Intent for the bot in the Discord Developer Portal "
    "(Bot > Privileged Gateway Intents)."
)


@functools.cache
def bot_directory() -> DiscordDirectory:
    """A DiscordDirectory with the bot token, for callers that have no Flask app, such as tools."""
    return DiscordDirectory(config.BOT_TOKEN)


def _ready(directory) -> Any:
    if directory is None or not directory.is_ready():
        raise MemberError(NO_DIRECTORY, 503)
    return directory


def server_roles(directory, guild_id) -> list[dict]:
    """The server roles that a member sync can filter by. Raises MemberError when Discord cannot answer."""
    try:
        return discord_roles(_ready(directory), guild_id)
    except DiscordUnavailable as e:
        logger.warning("role lookup failed for guild %s: %s", guild_id, e)
        raise MemberError("Discord did not answer the role list.", 503) from e


def sync_from_discord(db, organization_id: int, guild_id, directory, roles: object, dry_run: bool) -> dict:
    """Add the server members that hold one of roles (all members when roles is empty) to the org's members."""
    if not isinstance(roles, list) or not all(isinstance(r, str) and r.isdigit() for r in roles):
        raise MemberError("roles must be a list of role ids")
    try:
        members = _ready(directory).list_members(guild_id)
    except DiscordUnavailable as e:
        logger.warning("member list failed for org %s: %s", organization_id, e)
        if "403" in str(e):
            raise MemberError(NO_MEMBERS_INTENT, 503) from e
        raise MemberError("Discord did not answer the member list. Try again shortly.", 503) from e
    chosen = [m for m in members if not roles or set(roles) & set(m.get("roles", []))]
    return sync_discord_members(db, organization_id, chosen, dry_run=dry_run)


def discord_roles(directory, guild_id) -> list[dict]:
    """Roles a member filter can use, highest first. The everyone role and roles that bots manage are left out."""
    roles = [r for r in directory.get_guild_roles(guild_id) if r["id"] != str(guild_id) and not r["managed"]]
    roles.sort(key=lambda r: -r["position"])
    return [{"id": r["id"], "name": r["name"], "color": r["color"]} for r in roles]


def _chunks(values: list, size: int = SYNC_CHUNK):
    for start in range(0, len(values), size):
        yield values[start : start + size]


def sync_discord_members(db, organization_id: int, members: list[dict], dry_run: bool = False) -> dict:
    """Make each Discord member a member of the org. Commits unless dry_run.

    members are rows from DiscordDirectory.list_members. A person with no user row gets one with their Discord id,
    name and username; the username is left empty when another user has it. A removed membership is made active
    again. Returns counts: matched, new_users, joined (new or active again) and already.
    """
    wanted = {str(m["id"]): m for m in members if str(m.get("id", "")).isdigit() and not m.get("bot")}
    ids = list(wanted)
    users: dict[str, User] = {}
    for chunk in _chunks(ids):
        users |= {str(u.discord_id): u for u in db.query(User).filter(User.discord_id.in_(chunk)).all()}
    memberships: dict[int, UserOrganizationMembership] = {}
    user_ids = [int(u.id) for u in users.values()]
    for chunk in _chunks(user_ids):
        rows = (
            db.query(UserOrganizationMembership)
            .filter(
                UserOrganizationMembership.organization_id == organization_id,
                UserOrganizationMembership.user_id.in_(chunk),
            )
            .all()
        )
        memberships |= {int(cast(int, m.user_id)): m for m in rows}
    usernames = [str(wanted[i].get("username")) for i in ids if i not in users and wanted[i].get("username")]
    taken: set[str] = set()
    for chunk in _chunks(usernames):
        taken |= {str(name) for (name,) in db.query(User.username).filter(User.username.in_(chunk)).all()}

    counts = {"matched": len(ids), "new_users": 0, "joined": 0, "already": 0}
    for discord_id in ids:
        member = wanted[discord_id]
        user = users.get(discord_id)
        if user is None:
            counts["new_users"] += 1
            counts["joined"] += 1
            if dry_run:
                continue
            username = member.get("username")
            if not username or username in taken:
                username = None
            else:
                taken.add(username)
            user = User(discord_id=discord_id, username=username, name=member.get("name"), uuid=str(uuid.uuid4()))
            db.add(user)
            db.flush()
            db.add(UserOrganizationMembership(user_id=user.id, organization_id=organization_id))
            continue
        membership = memberships.get(int(user.id))
        if membership is not None and membership.is_active:
            counts["already"] += 1
            continue
        counts["joined"] += 1
        if dry_run:
            continue
        if membership is None:
            db.add(UserOrganizationMembership(user_id=user.id, organization_id=organization_id))
        else:
            membership.is_active = True
    if not dry_run:
        db.commit()
    logger.info("discord member sync org=%s dry_run=%s counts=%s", organization_id, dry_run, counts)
    return counts
