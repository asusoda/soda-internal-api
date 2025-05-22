# SoDA API Logging System

This project uses a centralized, color-formatted logging system.

## Features

- Color-coded log output by log level
- Standardized logging format across all modules
- Consistent naming for module loggers
- Exception traceback capture with `exc_info=True`

## Usage

To use the logging system in a new or existing module:

```python
from shared import get_logger

# Get module logger with appropriate namespace
logger = get_logger("module.submodule")

# Use the logger
logger.debug("Debug information")
logger.info("Informational message")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical error")

# Include exception info
try:
    # Some code that might raise an exception
    result = some_function()
except Exception as e:
    logger.error(f"Error in operation: {e}", exc_info=True)
```

## Log Format

Logs appear in the following format:
```
[2023-07-15 14:30:45] INFO     module.name     Log message here
```

With color-coding:
- DEBUG: Cyan
- INFO: Green
- WARNING: Yellow
- ERROR: Red
- CRITICAL: Red with white background

## Dependencies

Install the required dependencies with:
```
pip install -r logging-requirements.txt
``` 