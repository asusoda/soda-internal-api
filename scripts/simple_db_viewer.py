#!/usr/bin/env python3
"""
Simple Database Viewer
A lightweight script to visualize the consolidated user.db database without external dependencies.
"""

import os
import sqlite3
import sys
from datetime import datetime

def get_db_path():
    """Get the database file path."""
    db_path = "./data/user.db"
    if not os.path.exists(db_path):
        print(f"❌ Database file not found at: {db_path}")
        print("Make sure the database exists and the path is correct.")
        return None
    return db_path

def print_separator(char="=", length=60):
    """Print a separator line."""
    print(char * length)

def format_value(value, max_length=30):
    """Format a value for display."""
    if value is None:
        return "NULL"
    elif isinstance(value, str):
        if len(value) > max_length:
            return value[:max_length-3] + "..."
        return value
    else:
        return str(value)

def show_database_overview():
    """Show an overview of the database."""
    db_path = get_db_path()
    if not db_path:
        return
    
    print("🔍 Database Overview")
    print_separator()
    print(f"📁 Database: {db_path}")
    print(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        if not tables:
            print("❌ No tables found in the database.")
            return
        
        print(f"📊 Found {len(tables)} tables:")
        for i, table in enumerate(tables, 1):
            print(f"   {i}. {table}")
        print()
        
        # Show table details
        for table_name in tables:
            print(f"📋 Table: {table_name}")
            print("-" * 40)
            
            # Get schema
            cursor.execute(f"PRAGMA table_info({table_name});")
            schema = cursor.fetchall()
            
            print("Schema:")
            print(f"{'Column':<20} {'Type':<15} {'Null':<8} {'Key':<12}")
            print("-" * 60)
            for col in schema:
                col_name = col[1]
                col_type = col[2]
                col_null = "NOT NULL" if col[3] else "NULL"
                col_key = "PRIMARY KEY" if col[5] else ""
                print(f"{col_name:<20} {col_type:<15} {col_null:<8} {col_key:<12}")
            print()
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            row_count = cursor.fetchone()[0]
            print(f"📈 Row count: {row_count}")
            
            # Show sample data
            if row_count > 0:
                print("Sample data (first 5 rows):")
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 5;")
                rows = cursor.fetchall()
                
                if rows:
                    # Get column names
                    columns = [col[1] for col in schema]
                    
                    # Print header
                    header = " | ".join(f"{col:<15}" for col in columns)
                    print("-" * len(header))
                    print(header)
                    print("-" * len(header))
                    
                    # Print data
                    for row in rows:
                        formatted_row = []
                        for value in row:
                            formatted_row.append(f"{format_value(value, 15):<15}")
                        print(" | ".join(formatted_row))
                    
                    print("-" * len(header))
            else:
                print("No data in table")
            
            print("\n" + "=" * 60 + "\n")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")

def show_table_details(table_name):
    """Show detailed information about a specific table."""
    db_path = get_db_path()
    if not db_path:
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
        if not cursor.fetchone():
            print(f"❌ Table '{table_name}' not found.")
            return
        
        print(f"📋 Detailed view of table: {table_name}")
        print_separator()
        
        # Get schema
        cursor.execute(f"PRAGMA table_info({table_name});")
        schema = cursor.fetchall()
        
        print("Schema:")
        print(f"{'Column':<20} {'Type':<15} {'Null':<8} {'Key':<12} {'Default':<15}")
        print("-" * 75)
        for col in schema:
            col_name = col[1]
            col_type = col[2]
            col_null = "NOT NULL" if col[3] else "NULL"
            col_key = "PRIMARY KEY" if col[5] else ""
            col_default = str(col[4]) if col[4] else ""
            print(f"{col_name:<20} {col_type:<15} {col_null:<8} {col_key:<12} {col_default:<15}")
        print()
        
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        row_count = cursor.fetchone()[0]
        print(f"📈 Total rows: {row_count}")
        
        if row_count > 0:
            # Show all data (with pagination for large tables)
            page_size = 20
            total_pages = (row_count + page_size - 1) // page_size
            
            for page in range(min(total_pages, 3)):  # Show max 3 pages
                offset = page * page_size
                cursor.execute(f"SELECT * FROM {table_name} LIMIT {page_size} OFFSET {offset};")
                rows = cursor.fetchall()
                
                # Get column names
                columns = [col[1] for col in schema]
                
                print(f"\n📄 Page {page + 1} (rows {offset + 1}-{min(offset + page_size, row_count)}):")
                print("-" * 80)
                
                # Print header
                header = " | ".join(f"{col:<20}" for col in columns)
                print(header)
                print("-" * len(header))
                
                # Print data
                for row in rows:
                    formatted_row = []
                    for value in row:
                        formatted_row.append(f"{format_value(value, 20):<20}")
                    print(" | ".join(formatted_row))
                
                print("-" * len(header))
                
                if page < 2 and total_pages > 3:
                    print(f"\n... and {total_pages - 3} more pages")
                    break
        else:
            print("No data in table")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")

def show_database_stats():
    """Show database statistics."""
    db_path = get_db_path()
    if not db_path:
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("📊 Database Statistics")
        print_separator()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"{'Table':<25} {'Rows':<10} {'Columns':<10}")
        print("-" * 45)
        
        total_rows = 0
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table};")
            row_count = cursor.fetchone()[0]
            total_rows += row_count
            
            # Get table size info
            cursor.execute(f"PRAGMA table_info({table});")
            column_count = len(cursor.fetchall())
            
            print(f"{table:<25} {row_count:<10} {column_count:<10}")
        
        print("-" * 45)
        print(f"{'TOTAL':<25} {total_rows:<10} {len(tables):<10}")
        
        print(f"\n📈 Total rows across all tables: {total_rows}")
        print(f"📋 Total tables: {len(tables)}")
        
        # File size
        file_size = os.path.getsize(db_path)
        print(f"💾 Database file size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")

def show_available_tables():
    """Show list of available tables."""
    db_path = get_db_path()
    if not db_path:
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        print("📋 Available Tables:")
        print_separator()
        
        if not tables:
            print("No tables found in the database.")
        else:
            for i, table in enumerate(tables, 1):
                cursor.execute(f"SELECT COUNT(*) FROM {table};")
                row_count = cursor.fetchone()[0]
                print(f"{i:2}. {table:<25} ({row_count} rows)")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")

def main():
    """Main function to run the visualization tool."""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "overview":
            show_database_overview()
        elif command == "stats":
            show_database_stats()
        elif command == "tables":
            show_available_tables()
        elif command == "table" and len(sys.argv) > 2:
            table_name = sys.argv[2]
            show_table_details(table_name)
        else:
            print("Usage:")
            print("  python simple_db_viewer.py overview  - Show database overview")
            print("  python simple_db_viewer.py stats     - Show database statistics")
            print("  python simple_db_viewer.py tables    - Show available tables")
            print("  python simple_db_viewer.py table <table_name>  - Show table details")
    else:
        # Default: show overview
        show_database_overview()

if __name__ == "__main__":
    main() 