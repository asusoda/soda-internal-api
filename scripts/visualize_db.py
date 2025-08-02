#!/usr/bin/env python3
"""
Database Visualization Script
This script helps visualize the structure and data of the consolidated user.db database.
"""

import os
import sqlite3
import sys
from datetime import datetime
from tabulate import tabulate

def get_db_path():
    """Get the database file path."""
    db_path = "./data/user.db"
    if not os.path.exists(db_path):
        print(f"❌ Database file not found at: {db_path}")
        print("Make sure the database exists and the path is correct.")
        return None
    return db_path

def get_table_info(cursor):
    """Get information about all tables in the database."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    return tables

def get_table_schema(cursor, table_name):
    """Get the schema for a specific table."""
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = cursor.fetchall()
    return columns

def get_table_data(cursor, table_name, limit=10):
    """Get sample data from a table."""
    try:
        cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit};")
        rows = cursor.fetchall()
        
        # Get column names
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = [col[1] for col in cursor.fetchall()]
        
        return columns, rows
    except sqlite3.Error as e:
        return [], []

def format_table_data(columns, rows):
    """Format table data for display."""
    if not rows:
        return "No data found"
    
    # Convert rows to list of lists for tabulate
    formatted_rows = []
    for row in rows:
        formatted_row = []
        for value in row:
            if value is None:
                formatted_row.append("NULL")
            elif isinstance(value, str) and len(value) > 50:
                formatted_row.append(value[:47] + "...")
            else:
                formatted_row.append(str(value))
        formatted_rows.append(formatted_row)
    
    return tabulate(formatted_rows, headers=columns, tablefmt="grid")

def show_database_overview():
    """Show an overview of the database."""
    db_path = get_db_path()
    if not db_path:
        return
    
    print("🔍 Database Visualization Tool")
    print("=" * 50)
    print(f"📁 Database: {db_path}")
    print(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        tables = get_table_info(cursor)
        
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
            print("-" * 30)
            
            # Get schema
            schema = get_table_schema(cursor, table_name)
            print("Schema:")
            schema_data = []
            for col in schema:
                schema_data.append([
                    col[1],  # name
                    col[2],  # type
                    "NOT NULL" if col[3] else "NULL",
                    "PRIMARY KEY" if col[5] else ""
                ])
            print(tabulate(schema_data, headers=["Column", "Type", "Null", "Key"], tablefmt="simple"))
            print()
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            row_count = cursor.fetchone()[0]
            print(f"📈 Row count: {row_count}")
            
            # Show sample data
            if row_count > 0:
                print("Sample data:")
                columns, rows = get_table_data(cursor, table_name, limit=5)
                if columns and rows:
                    print(format_table_data(columns, rows))
            else:
                print("No data in table")
            
            print("\n" + "=" * 50 + "\n")
        
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
        print("=" * 50)
        
        # Get schema
        schema = get_table_schema(cursor, table_name)
        print("Schema:")
        schema_data = []
        for col in schema:
            schema_data.append([
                col[1],  # name
                col[2],  # type
                "NOT NULL" if col[3] else "NULL",
                "PRIMARY KEY" if col[5] else "",
                col[4] if col[4] else ""  # default value
            ])
        print(tabulate(schema_data, headers=["Column", "Type", "Null", "Key", "Default"], tablefmt="grid"))
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
                cursor.execute(f"PRAGMA table_info({table_name});")
                columns = [col[1] for col in cursor.fetchall()]
                
                print(f"\n📄 Page {page + 1} (rows {offset + 1}-{min(offset + page_size, row_count)}):")
                print(format_table_data(columns, rows))
                
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
        print("=" * 30)
        
        # Get all tables
        tables = get_table_info(cursor)
        
        stats_data = []
        total_rows = 0
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table};")
            row_count = cursor.fetchone()[0]
            total_rows += row_count
            
            # Get table size info
            cursor.execute(f"PRAGMA table_info({table});")
            column_count = len(cursor.fetchall())
            
            stats_data.append([table, row_count, column_count])
        
        print(tabulate(stats_data, headers=["Table", "Rows", "Columns"], tablefmt="grid"))
        print(f"\n📈 Total rows across all tables: {total_rows}")
        print(f"📋 Total tables: {len(tables)}")
        
        # File size
        file_size = os.path.getsize(db_path)
        print(f"💾 Database file size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
        
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
        elif command == "table" and len(sys.argv) > 2:
            table_name = sys.argv[2]
            show_table_details(table_name)
        else:
            print("Usage:")
            print("  python visualize_db.py overview  - Show database overview")
            print("  python visualize_db.py stats     - Show database statistics")
            print("  python visualize_db.py table <table_name>  - Show table details")
    else:
        # Default: show overview
        show_database_overview()

if __name__ == "__main__":
    main() 