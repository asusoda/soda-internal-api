from typing import List, Callable
import importlib
import pkgutil
import os

def get_all_migrations() -> List[Callable]:
    """Get all migration functions from the migrations package"""
    migrations = []
    
    # Get the directory of this file
    migrations_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Iterate through all subdirectories
    for _, name, _ in pkgutil.iter_modules([migrations_dir]):
        try:
            # Import the module
            module = importlib.import_module(f"migrations.{name}")
            # Get the run_migration function if it exists
            if hasattr(module, "run_migration"):
                migrations.append(module.run_migration)
        except ImportError as e:
            print(f"Error importing migration module {name}: {str(e)}")
    
    return migrations

def run_all_migrations():
    """Run all available migrations"""
    migrations = get_all_migrations()
    print(f"Found {len(migrations)} migration(s) to run")
    
    for migration in migrations:
        try:
            migration()
        except Exception as e:
            print(f"Error running migration: {str(e)}")
            raise 