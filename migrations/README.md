# Database Migrations

This directory contains database migration scripts for the Soda Internal API. Migrations are automatically run when the application starts.

## Structure

```
migrations/
├── __init__.py           # Migration discovery and execution
└── [module_name]/        # Module-specific migrations
    ├── __init__.py       # Exposes run_migration() function
    ├── create_tables.sql # SQL migration script
    └── run_migration.py  # Python migration runner
```

## Creating New Migrations

To add a new migration:

1. Create a new directory under `migrations/` for your module:
   ```bash
   mkdir migrations/your_module
   ```

2. Create the following files:
   - `__init__.py`:
     ```python
     from .run_migration import run_your_migration

     def run_migration():
         """Run the your_module migrations"""
         run_your_migration()
     ```
   
   - `create_tables.sql`: Your SQL migration script
   - `run_migration.py`: Python script to execute the SQL

3. Follow these guidelines for SQL migrations:
   - Use `IF NOT EXISTS` for all CREATE statements
   - Include appropriate indexes
   - Add foreign key constraints where needed
   - Use consistent naming conventions:
     - Tables: lowercase with underscores
     - Indexes: `idx_table_name_column_name`

## Example Migration

Here's an example migration structure:

```
migrations/example/
├── __init__.py
├── create_tables.sql
└── run_migration.py
```

### create_tables.sql
```sql
-- Create example table
CREATE TABLE IF NOT EXISTS example_table (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_example_table_name ON example_table(name);
```

### run_migration.py
```python
import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from shared.config import config

def run_example_migration():
    """Execute the SQL migration script"""
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        sql_file = os.path.join(current_dir, 'create_tables.sql')
        
        with open(sql_file, 'r') as f:
            sql_commands = f.read()

        conn = psycopg2.connect(
            dbname=config.DB_NAME,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            host=config.DB_HOST,
            port=config.DB_PORT
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        with conn.cursor() as cur:
            cur.execute(sql_commands)
        
        print("Example migrations completed successfully!")
        
    except Exception as e:
        print(f"Error during example migration: {str(e)}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()
```

## Best Practices

1. **Idempotency**: All migrations should be idempotent (safe to run multiple times)
2. **Atomicity**: Each migration should be atomic (all-or-nothing)
3. **Backward Compatibility**: Avoid breaking changes to existing tables
4. **Documentation**: Document all new tables and columns
5. **Testing**: Test migrations in a development environment first

## Dependencies

- `psycopg2-binary`: Required for running migrations
- Database credentials from `shared.config`

## Running Migrations

Migrations are automatically run when the application starts. To run them manually:

```python
from migrations import run_all_migrations
run_all_migrations()
``` 