import logging
import colorlog

# Configure logging with colors and improved formatting
def setup_logger():
    """Configure and return the root logger with color formatting"""
    handler = colorlog.StreamHandler()
    formatter = colorlog.ColoredFormatter(
        fmt='%(log_color)s[%(asctime)s] %(levelname)-8s %(name)-20s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove existing handlers to avoid duplicates
    for hdlr in root_logger.handlers:
        root_logger.removeHandler(hdlr)
    
    root_logger.addHandler(handler)
    return root_logger

# Initialize root logger
logger = setup_logger()

def get_logger(name):
    """Get a logger for a specific module with proper formatting"""
    return logging.getLogger(name) 