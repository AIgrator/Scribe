import logging
import os


def setup_logging(log_to_file=False, log_file_path="app.log", log_level="INFO"):
    handlers = [logging.StreamHandler()]
    log_error = None
    if log_to_file:
        log_file_path = os.path.abspath(log_file_path)
        try:
            parent = os.path.dirname(log_file_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            handlers.append(logging.FileHandler(log_file_path, encoding="utf-8"))
        except Exception as e:
            # Console logging still works; do not take the app down over a log file.
            log_error = e
    # Convert log_level string to logging constant
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="[%(levelname)s] %(filename)s: %(message)s",
        handlers=handlers
    )
    if log_error is not None:
        logging.getLogger(__name__).error(f"Failed to open log file {log_file_path}: {log_error}")
