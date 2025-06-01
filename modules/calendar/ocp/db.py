"""
This module provides backward compatibility for code that still imports the OCPDBConnect
class directly. It redirects to the centralized database manager in modules.utils.db.
"""

import logging
from shared import ocp_db_manager
from modules.utils.db import OCPDBManager

# Set up a module logger
module_logger = logging.getLogger(__name__)
module_logger.info("OCP DB compatibility module loaded, using centralized database manager")

class OCPDBConnect:
    """
    Compatibility class that redirects to the centralized OCPDBManager.
    This class exists to maintain backward compatibility with code that
    might still import OCPDBConnect directly.
    """
    
    def __init__(self, db_url="sqlite:///./data/ocp.db"):
        """
        Initialize by logging a warning that we're using the compatibility layer.
        """
        module_logger.warning(
            "OCPDBConnect is deprecated, please use ocp_db_manager from shared.py instead"
        )
        # Nothing to do here, we'll delegate all methods to the centralized manager
        
    def __getattr__(self, name):
        """
        Delegate all method calls to the centralized database manager.
        This allows us to maintain backward compatibility without duplicating code.
        """
        if not ocp_db_manager:
            raise ValueError("Centralized OCP database manager is not initialized")
            
        if hasattr(ocp_db_manager, name):
            module_logger.debug(f"Redirecting {name} call to centralized database manager")
            return getattr(ocp_db_manager, name)
        else:
            raise AttributeError(f"Neither OCPDBConnect nor OCPDBManager has attribute '{name}'")

# For direct imports of objects from this module
get_db = ocp_db_manager.get_db if ocp_db_manager else None 