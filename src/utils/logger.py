import logging
import os
from typing import Optional

class Logger:
    """Application logging management."""
    
    def __init__(self):
        """Initialize the logger."""
        self.log_file = os.path.join(os.path.dirname(__file__), "..", "..", "app.log")
        self._setup_logger()
    
    def _setup_logger(self) -> None:
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def log(self, message: str, level: str = "info") -> None:
        """Log a message with the specified level."""
        level = level.lower()
        if level == "debug":
            self.logger.debug(message)
        elif level == "info":
            self.logger.info(message)
        elif level == "warning":
            self.logger.warning(message)
        elif level == "error":
            self.logger.error(message)
        elif level == "critical":
            self.logger.critical(message)
        else:
            self.logger.info(message)
    
    def log_exception(self, message: str, exc_info: Optional[Exception] = None) -> None:
        """Log an exception with full traceback."""
        self.logger.error(message, exc_info=exc_info)
    
    def clear_log(self) -> None:
        """Clear the log file."""
        try:
            with open(self.log_file, 'w') as f:
                f.write("")
        except Exception as e:
            self.log(f"Error clearing log file: {e}", "error") 