from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class OrganizationSettings:
    """Default settings for organizations."""
    # Discord integration settings
    enable_discord_integration: bool = True
    discord_bot_prefix: str = "!"
    discord_admin_roles: list = None
    discord_officer_roles: list = None
    
    # Points system settings
    enable_points_system: bool = True
    default_points_per_event: int = 10
    max_points_per_event: int = 100
    points_decay_rate: float = 0.0  # Percentage of points lost per month
    
    # Event management settings
    enable_event_management: bool = True
    require_event_approval: bool = True
    max_events_per_week: int = 5
    
    # Member management settings
    enable_member_management: bool = True
    require_member_verification: bool = True
    verification_method: str = "email"  # email, discord, or manual
    
    # Calendar settings
    enable_calendar_integration: bool = True
    calendar_sync_interval: int = 3600  # seconds
    
    def __post_init__(self):
        if self.discord_admin_roles is None:
            self.discord_admin_roles = []
        if self.discord_officer_roles is None:
            self.discord_officer_roles = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary."""
        return {
            "discord_integration": {
                "enabled": self.enable_discord_integration,
                "bot_prefix": self.discord_bot_prefix,
                "admin_roles": self.discord_admin_roles,
                "officer_roles": self.discord_officer_roles
            },
            "points_system": {
                "enabled": self.enable_points_system,
                "default_points": self.default_points_per_event,
                "max_points": self.max_points_per_event,
                "decay_rate": self.points_decay_rate
            },
            "event_management": {
                "enabled": self.enable_event_management,
                "require_approval": self.require_event_approval,
                "max_events": self.max_events_per_week
            },
            "member_management": {
                "enabled": self.enable_member_management,
                "require_verification": self.require_member_verification,
                "verification_method": self.verification_method
            },
            "calendar_integration": {
                "enabled": self.enable_calendar_integration,
                "sync_interval": self.calendar_sync_interval
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrganizationSettings':
        """Create settings from dictionary."""
        return cls(
            enable_discord_integration=data.get("discord_integration", {}).get("enabled", True),
            discord_bot_prefix=data.get("discord_integration", {}).get("bot_prefix", "!"),
            discord_admin_roles=data.get("discord_integration", {}).get("admin_roles", []),
            discord_officer_roles=data.get("discord_integration", {}).get("officer_roles", []),
            enable_points_system=data.get("points_system", {}).get("enabled", True),
            default_points_per_event=data.get("points_system", {}).get("default_points", 10),
            max_points_per_event=data.get("points_system", {}).get("max_points", 100),
            points_decay_rate=data.get("points_system", {}).get("decay_rate", 0.0),
            enable_event_management=data.get("event_management", {}).get("enabled", True),
            require_event_approval=data.get("event_management", {}).get("require_approval", True),
            max_events_per_week=data.get("event_management", {}).get("max_events", 5),
            enable_member_management=data.get("member_management", {}).get("enabled", True),
            require_member_verification=data.get("member_management", {}).get("require_verification", True),
            verification_method=data.get("member_management", {}).get("verification_method", "email"),
            enable_calendar_integration=data.get("calendar_integration", {}).get("enabled", True),
            calendar_sync_interval=data.get("calendar_integration", {}).get("sync_interval", 3600)
        ) 