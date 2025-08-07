"""
This module provides backward compatibility for code that still imports the OCPDBConnect
class directly. It redirects to the centralized database manager in modules.utils.db.
"""

import logging
import shared
from modules.utils.db import DBConnect
from modules.ocp.models import Officer, OfficerPoints

# Set up a module logger
module_logger = logging.getLogger(__name__)
module_logger.info("OCP DB compatibility module loaded, using centralized database manager")

def create_ocp_tables():
    """Create OCP tables if they do not exist."""
    from modules.utils.db import DBConnect
    db_connect = shared.db_connect or DBConnect()
    Officer.__table__.create(db_connect.engine, checkfirst=True)
    OfficerPoints.__table__.create(db_connect.engine, checkfirst=True)

# Automatically create OCP tables on import
try:
    create_ocp_tables()
    module_logger.info("OCP tables checked/created successfully.")
except Exception as e:
    module_logger.error(f"Error creating OCP tables: {e}")

class OCPDBConnect:
    """
    Compatibility class that redirects to the centralized DBConnect.
    This class exists to maintain backward compatibility with code that
    might still import OCPDBConnect directly.
    """
    
    def __init__(self, db_url="sqlite:///./data/user.db"):
        """
        Initialize by logging a warning that we're using the compatibility layer.
        """
        module_logger.warning(
            "OCPDBConnect is deprecated, please use db_connect from shared.py instead"
        )
        # Nothing to do here, we'll delegate all methods to the centralized manager
        
    def __getattr__(self, name):
        """
        Delegate all method calls to the centralized database manager.
        This allows us to maintain backward compatibility without duplicating code.
        """
        if not shared.db_connect:
            raise ValueError("Centralized database manager is not initialized")
            
        if hasattr(shared.db_connect, name):
            module_logger.debug(f"Redirecting {name} call to centralized database manager")
            return getattr(shared.db_connect, name)
        else:
            raise AttributeError(f"Neither OCPDBConnect nor DBConnect has attribute '{name}'")

# For direct imports of objects from this module
get_db = shared.db_connect.get_db if shared.db_connect else None 