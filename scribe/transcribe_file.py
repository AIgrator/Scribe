# transcribe_file.py
import logging
import os
import sys
import time

logger = logging.getLogger(__name__)

def get_transcribe_file(obj, transcribe_file_attr='_transcribe_file'):
    """Universal: obj is a class instance (usually self) that has a settings_manager.

    If transcribe_to_file is enabled in settings, creates a file and the records folder.
    Returns the opened file or None.
    """
    if not hasattr(obj, transcribe_file_attr):
        setattr(obj, transcribe_file_attr, None)
    transcribe_file = getattr(obj, transcribe_file_attr)
    if transcribe_file is not None:
        return transcribe_file
    # Get settings
    enabled = False
    settings = {}
    if hasattr(obj, 'settings_manager') and obj.settings_manager:
        sm = obj.settings_manager
        settings = sm.all() if hasattr(sm, 'all') else {}
        enabled = settings.get('transcribe_to_file', False)
    if enabled:
        ts = int(time.time())
        if getattr(sys, 'frozen', False):
            # If the application is run as a bundle, the PyInstaller bootloader
            # extends the sys module by a flag frozen=True and sets the app
            # path into variable _MEIPASS'.
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        records_dir = os.path.join(base_dir, 'records')
        # Always try to create the records folder
        if not os.path.exists(records_dir):
            try:
                os.makedirs(records_dir, exist_ok=True)
                logger.info(f"Records folder created: {records_dir}")
            except Exception as e:
                logger.error(f"Failed to create records folder: {e}")
        fname = os.path.join(records_dir, f"transcript_{ts}.txt")
        try:
            transcribe_file = open(fname, 'a', encoding='utf-8')
            setattr(obj, transcribe_file_attr, transcribe_file)
            logger.info(f"Transcription file opened: {fname}")
        except Exception as e:
            logger.error(f"Failed to open transcription file: {e}")
            setattr(obj, transcribe_file_attr, None)
    return getattr(obj, transcribe_file_attr)
