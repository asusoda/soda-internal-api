// Shapes of the pod (compute) API responses. The routes are in modules/godfather/api.py.

// _pod_dict() in modules/godfather/service.py.
export interface Pod {
  id: string;
  name: string;
  provider: string;
  // RUNNING, EXITED, GONE, UNKNOWN or another upper-case state of the provider.
  status: string;
  is_public: boolean;
  allowed_users: string[];
  created_by: string | null;
  created_at: string | null;
  machine: Record<string, unknown> | null;
  cost_per_hour: number | null;
}

// The actions that POST /pods/<pod_id>/action accepts (ACTIONS in modules/godfather/service.py).
export type PodAction = "start" | "stop" | "restart" | "terminate";

// session_dict() in modules/godfather/schedule.py.
export interface PodSession {
  id: number;
  pod_id: string;
  title: string | null;
  start_at: string;
  stop_at: string;
  started: boolean;
  finished: boolean;
  created_by: string | null;
}

// An item of PodFiles.list() in modules/godfather/files.py.
export interface PodFileEntry {
  name: string;
  type: "directory" | "file";
  size: number;
  modified: number;
  permissions: string;
}
