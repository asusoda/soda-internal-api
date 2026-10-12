// Calendar and LeetCode settings, and calendar events.

export type CalendarSettings = {
  notion_database_id: string | null;
  google_calendar_id: string | null;
  calendar_sync_enabled: boolean;
  last_sync_at: string | null;
};

// An event of the org's Notion calendar. Only id, title and start are always present.
export type CalendarEvent = {
  id: string;
  title: string;
  start: string;
  end?: string;
  location?: string;
  description?: string;
  gcal_id?: string;
  // The event's Google Calendar link, when a sync copied it there
  jump_url?: string;
};

export type LeetCodeSettings = { channel_id: string | null; role_ping: string | null; daily_time: string | null };
