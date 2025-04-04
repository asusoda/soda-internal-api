# Calendar Module TODO List

This document lists potential bugs, improvements, and areas for refactoring identified in `modules/calendar/api.py`.

## Potential Bugs & Risks

1.  (DONE) **Fragile Event Matching (Lines 186-203):**
    *   **Issue:** Matching events between Notion and Google Calendar relies only on `summary` and `start.dateTime`. Minor changes cause mismatches, leading to deletion and recreation of events.
    *   **Suggestion:** Store the Notion Page ID in a Google Calendar event's extended property or description and use it as the primary key for matching.

2.  **Risky Calendar Clearing (Lines 53-54, 255-280):**
    *   **Issue:** If `fetch_notion_events` returns empty (due to API errors, network issues, or no published future events), `clear_future_events` wipes *all* future events from Google Calendar.
    *   **Suggestion:** Add safeguards. Only clear events if the Notion API call was successful *and* explicitly returned zero events. Consider a "soft delete" mechanism or requiring confirmation.

3.  **Incorrect Calendar Creation Logic (Lines 79-98):**
    *   **Issue:** `ensure_calendar_access` *always* attempts to create a new calendar (`service.calendars().insert()`) instead of checking if the calendar specified in `config.GOOGLE_CALENDAR_ID` exists or searching for one by name.
    *   **Suggestion:** Modify the function to first try `service.calendars().get(calendarId=config.GOOGLE_CALENDAR_ID)`. If that fails, *then* attempt creation or search by name ('Notion Events'). Ensure the created calendar ID is stored/used consistently.

4.  **Faulty Default End Time Assumption (Lines 338-351):**
    *   **Issue:** Assumes a 1-hour duration for events missing an end time/date in Notion. This is incorrect for varying event lengths or all-day events.
    *   **Suggestion:** Properly handle Notion's representation of all-day events. Make the default duration configurable or infer based on event type if possible.

## Bad Practices & Areas for Improvement

5.  **Security TODO (Line 35):**
    *   **Issue:** Explicit `TODO` for secure storage of the Notion webhook verification token is unimplemented.
    *   **Suggestion:** Implement secure storage (e.g., environment variable, secrets manager, database) for the token.

6.  **Inefficient Deletion (Lines 152-157, 271-276):**
    *   **Issue:** Events are deleted individually in loops (`clear_future_events` and `update_google_calendar`). This is inefficient for many events.
    *   **Suggestion:** Investigate and use Google Calendar API batch endpoints for deletions if available.

7.  **Hardcoded Calendar Name (Line 87):**
    *   **Issue:** The calendar name 'Notion Events' is hardcoded in `ensure_calendar_access`.
    *   **Suggestion:** Make the calendar name configurable, potentially via `shared/config.py`.

8.  **Webhook Database ID Override (Line 39):**
    *   **Issue:** The webhook allows overriding `config.NOTION_DATABASE_ID` via the request payload.
    *   **Suggestion:** Review if this flexibility is necessary and ensure appropriate security/validation if the endpoint is publicly accessible.

9.  **Basic Rich Text Handling (Line 322):**
    *   **Issue:** `extract_property` only gets text from the *first* item in a `rich_text` or `title` array, losing subsequent formatted text or mentions.
    *   **Suggestion:** Modify the helper to concatenate content from all relevant objects within the `rich_text`/`title` array.

10. **Error Handling Specificity:**
    *   **Issue:** Generic `except Exception` blocks are used widely.
    *   **Suggestion:** Catch more specific exceptions (e.g., `googleapiclient.errors.HttpError`, `notion_client.APIResponseError`) for better error reporting and potentially different handling logic.