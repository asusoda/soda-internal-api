// Shapes of the API responses that more than one page uses.

// Organization.to_dict() in modules/organizations/models.py.
export interface Organization {
  id: number;
  name: string;
  prefix: string;
  guild_id: string;
  description: string | null;
  icon_url: string | null;
  is_active: boolean;
  officer_role_id: string | null;
  points_per_message: number | null;
  points_cooldown: number | null;
  google_calendar_id: string | null;
  notion_database_id: string | null;
  calendar_sync_enabled: boolean;
  last_sync_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

// GET /api/auth/name
export interface AuthUser {
  name: string;
}

// The error body of most routes.
export interface ApiError {
  error?: string;
  message?: string;
}
