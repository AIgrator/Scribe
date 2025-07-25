# command_handler.py
import logging
import os
import subprocess

import keyboard

from scribe.text_utils import fuzzy_match, normalize_text

logger = logging.getLogger(__name__)


def command_mode(settings_manager, lang=None):
    """Returns a handler for command mode.

    settings_manager — settings object
    lang — command language (defaults to current from settings).
    """
    def handler(text):
        settings = settings_manager.all() if hasattr(settings_manager, 'all') else {}
        lang_code = lang or settings.get('language', 'en')
        text_norm = normalize_text(text)
        logger.info(f"[COMMAND] Recognized text: '{text_norm}'")
        # 1. Check commands_hotkey
        fuzzy_threshold_hotkey = float(settings.get('fuzzy_match_hotkey', 90)) / 100.0
        hotkey_cmds = settings.get('commands_hotkey', {}).get(lang_code, [])
        for cmd in hotkey_cmds:
            trigger = normalize_text(cmd.get('trigger', ''))
            hotkey = cmd.get('hotkey', '').strip()
            logger.debug(f"[COMMAND] Checking hotkey trigger: '{trigger}' ~ '{text_norm}'")
            # First exact match, then fuzzy_match
            if trigger and (trigger == text_norm or fuzzy_match(trigger, text_norm, threshold=fuzzy_threshold_hotkey)):
                if hotkey:
                    logger.info(f"[COMMAND] Simulating hotkey: {hotkey}")
                    try:
                        keyboard.send(hotkey)
                    except Exception as e:
                        logger.error(f"[COMMAND][ERROR] Failed to send hotkey: {e}")
                return  # Only execute the first match
        # 2. Check commands_openfile
        fuzzy_threshold_openfile = float(
            settings.get('fuzzy_match_openfile', 90)) / 100.0
        openfile_cmds = settings.get('commands_openfile', {}).get(lang_code, [])
        for cmd in openfile_cmds:
            trigger = normalize_text(cmd.get('trigger', ''))
            path = cmd.get('path', '').strip()
            args = cmd.get('args', '').strip()
            # Check for the 'is_uwp' flag, defaulting to False if not present
            is_uwp = str(cmd.get('is_uwp', 'false')).lower() == 'true'

            logger.debug(
                f"[COMMAND] Checking openfile trigger: '{trigger}' ~ '{text_norm}'")
            # First exact match, then fuzzy_match
            if trigger and (trigger == text_norm or fuzzy_match(trigger, text_norm, threshold=fuzzy_threshold_openfile)):
                # The launch logic now depends on whether it's a UWP app or a regular file.
                if is_uwp:
                    # For UWP/Shell apps, the 'args' field contains the shell URI.
                    if args:
                        logger.info(f"[COMMAND] Launching UWP/Shell app: {args}")
                        try:
                            # The launch method differs between Windows versions.
                            if os.name == 'nt':
                                import sys
                                win_ver = sys.getwindowsversion()

                                # For Win 10 (major version 10) and 11, explorer.exe is reliable.
                                if win_ver.major >= 10:
                                    logger.debug("Using 'explorer.exe' method for Windows 10/11.")
                                    subprocess.Popen(['explorer.exe', args])
                                # For Win 8.0 (6.2), os.startfile was confirmed to work.
                                else:
                                    logger.debug("Using 'os.startfile' method for Windows 8.0.")
                                    os.startfile(args)
                            else:
                                logger.warning("[COMMAND][WARN] UWP launch attempted on non-Windows OS.")
                        except Exception as e:
                            logger.error(
                                f"[COMMAND][ERROR] Failed to launch UWP/Shell app: {e}")
                    else:
                        logger.warning(
                            f"[COMMAND][WARN] UWP app has no launch arguments: {trigger}")
                elif path:
                    # This is the original logic for standard executables.
                    logger.info(f"[COMMAND] Launching file: {path} {args}")
                    try:
                        # If it's on Windows and no arguments — use os.startfile
                        if os.name == 'nt' and not args:
                            os.startfile(path)
                        else:
                            # For cross-platform or with-args, use Popen.
                            subprocess.Popen([path] + args.split())
                    except Exception as e:
                        logger.error(
                            f"[COMMAND][ERROR] Failed to launch file: {e}")
                return  # Execute only the first match
    return handler
