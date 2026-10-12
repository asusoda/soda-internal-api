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

// A member with the fields of member_fields() in modules/users/service.py. asu_id and academic_standing are the
// legacy keys of student_id and class_standing.
export interface MemberDetails {
  id: number;
  name: string | null;
  email: string | null;
  username: string | null;
  asu_id: string | null;
  academic_standing: string | null;
  student_id: string | null;
  class_standing: string | null;
  major: string | null;
  profile_fields: Record<string, string | number | boolean>;
}

// The member fields that the edit forms show, as PUT /api/points/<org_prefix>/users/<user_identifier> takes them.
export type MemberEditFields = {
  name: string;
  asu_id: string;
  academic_standing: string;
  major: string;
};

// The fields of next that differ from before. A blank ASU ID becomes null, because student_id is unique.
export const changedMemberFields = (
  before: Readonly<Record<string, string | undefined>>,
  next: Readonly<Record<string, string | undefined>>,
): Record<string, string | null> => {
  const changes: Record<string, string | null> = {};
  for (const [key, value] of Object.entries(next)) {
    if (value === undefined || value === before[key]) continue;
    changes[key] = key === 'asu_id' && value.trim() === '' ? null : value;
  }
  return changes;
};

// GET /api/points/<org_prefix>/users/<user_identifier>/points
export interface UserPointsResponse {
  user: MemberDetails;
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
