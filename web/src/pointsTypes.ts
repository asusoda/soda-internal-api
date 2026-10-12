// Shapes of the points API responses that more than one page uses.

// One entry of history_json() in modules/points/service.py.
export interface PointHistoryEntry {
  id: number;
  points: number | null;
  event: string | null;
  awarded_by_officer: string | null;
  timestamp: string | null;
  last_updated: string | null;
}

// GET /api/points/<org_prefix>/users/<user_identifier>/points
export interface UserPointsResponse {
  user: {
    id: number;
    name: string | null;
    email: string | null;
    username: string | null;
  };
  organization: {
    name: string;
    prefix: string;
  };
  total_points: number;
  points_history: PointHistoryEntry[];
}

// The body of a points route that reports what it did.
export interface MessageResponse {
  message?: string;
}
