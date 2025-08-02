# Database Visualization Scripts

This folder contains scripts to help visualize and explore the consolidated `user.db` database.

## Scripts

### 1. `simple_db_viewer.py` (Recommended)
A lightweight database viewer that doesn't require external dependencies.

**Usage:**
```bash
# Show database overview (default)
python scripts/simple_db_viewer.py

# Show database overview
python scripts/simple_db_viewer.py overview

# Show database statistics
python scripts/simple_db_viewer.py stats

# Show available tables
python scripts/simple_db_viewer.py tables

# Show detailed view of a specific table
python scripts/simple_db_viewer.py table users
python scripts/simple_db_viewer.py table officers
python scripts/simple_db_viewer.py table officer_points
```

**Features:**
- ✅ No external dependencies
- ✅ Shows table schemas
- ✅ Shows sample data
- ✅ Shows row counts
- ✅ Paginated data display
- ✅ Database statistics

### 2. `visualize_db.py` (Advanced)
A more advanced database viewer with better formatting using the `tabulate` library.

**Requirements:**
```bash
pip install tabulate
```

**Usage:**
```bash
# Show database overview
python scripts/visualize_db.py overview

# Show database statistics
python scripts/visualize_db.py stats

# Show detailed view of a specific table
python scripts/visualize_db.py table users
```

**Features:**
- ✅ Better table formatting with `tabulate`
- ✅ Grid-style output
- ✅ More detailed schema information
- ✅ Better data truncation

## Database Tables

The consolidated database contains the following tables:

### User Management
- `users` - User accounts and profiles
- `points` - User points/achievements

### Officer Management (OCP)
- `officers` - Officer profiles and information
- `officer_points` - Officer contribution points

### Calendar Management
- `calendar_event_links` - Links between Notion and Google Calendar events

### Game Management
- `jeopardy_game` - Jeopardy game data
- `active_game` - Active game sessions

## Examples

### View Database Overview
```bash
python scripts/simple_db_viewer.py overview
```

Output:
```
🔍 Database Overview
============================================================
📁 Database: ./data/user.db
📅 Generated: 2024-01-15 10:30:45

📊 Found 7 tables:
   1. users
   2. points
   3. officers
   4. officer_points
   5. calendar_event_links
   6. jeopardy_game
   7. active_game

📋 Table: users
----------------------------------------
Schema:
Column               Type            Null     Key
------------------------------------------------------------
email               String          NOT NULL PRIMARY KEY
uuid                String          NOT NULL
asu_id              String          NULL
name                String          NOT NULL
academic_standing   String          NOT NULL
major               String          NOT NULL

📈 Row count: 5
Sample data (first 5 rows):
------------------------------------------------------------
email           | uuid           | asu_id        | name          | academic_standing | major
------------------------------------------------------------
john@asu.edu    | abc-123-def    | 123456789     | John Doe      | Senior           | Computer Science
jane@asu.edu    | def-456-ghi    | 987654321     | Jane Smith    | Junior           | Engineering
------------------------------------------------------------
```

### View Table Details
```bash
python scripts/simple_db_viewer.py table officers
```

### View Database Statistics
```bash
python scripts/simple_db_viewer.py stats
```

## Tips

1. **Start with overview**: Use `overview` to get a quick summary of all tables
2. **Check specific tables**: Use `table <table_name>` to see detailed data
3. **Use statistics**: Use `stats` to see row counts and file size
4. **List tables**: Use `tables` to see all available tables with row counts

## Troubleshooting

### Database not found
If you get "Database file not found" error:
- Make sure the database exists at `./data/user.db`
- Check that the application has been run at least once to create the database

### Permission errors
- Make sure you have read permissions for the database file
- On Windows, run as administrator if needed

### Import errors
- The `simple_db_viewer.py` script uses only standard Python libraries
- For `visualize_db.py`, install tabulate: `pip install tabulate` 