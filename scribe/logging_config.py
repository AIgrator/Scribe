import logging


def setup_logging(log_to_file=False, log_file_path="app.log", log_level="INFO"):
    handlers = [logging.StreamHandler()]
    if log_to_file:
        handlers.append(logging.FileHandler(log_file_path, encoding="utf-8"))
    # Convert log_level string to logging constant
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="[%(levelname)s] %(filename)s: %(message)s",
        handlers=handlers
    )
