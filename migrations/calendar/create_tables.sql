-- Create calendar_events table
CREATE TABLE IF NOT EXISTS calendar_events (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    location VARCHAR(255),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    timezone VARCHAR(50) DEFAULT 'UTC',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_published BOOLEAN DEFAULT TRUE,
    guests JSONB,
    metadata JSONB,
    notion_event_id VARCHAR(255) UNIQUE,
    google_calendar_event_id VARCHAR(255) UNIQUE
);

-- Create notion_events table
CREATE TABLE IF NOT EXISTS notion_events (
    id SERIAL PRIMARY KEY,
    notion_page_id VARCHAR(255) UNIQUE NOT NULL,
    notion_database_id VARCHAR(255) NOT NULL,
    last_edited_time TIMESTAMP,
    properties JSONB,
    calendar_event_id INTEGER REFERENCES calendar_events(id)
);

-- Create google_events table
CREATE TABLE IF NOT EXISTS google_events (
    id SERIAL PRIMARY KEY,
    google_event_id VARCHAR(255) UNIQUE NOT NULL,
    calendar_id VARCHAR(255) NOT NULL,
    etag VARCHAR(255),
    html_link VARCHAR(255),
    calendar_event_id INTEGER REFERENCES calendar_events(id)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_calendar_events_notion_id ON calendar_events(notion_event_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_google_id ON calendar_events(google_calendar_event_id);
CREATE INDEX IF NOT EXISTS idx_notion_events_page_id ON notion_events(notion_page_id);
CREATE INDEX IF NOT EXISTS idx_google_events_event_id ON google_events(google_event_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_dates ON calendar_events(start_time, end_time); 