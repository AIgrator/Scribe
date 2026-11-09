# Section 6: Settings — General and System

The settings window has two tabs for everyday options: **General** and **System**.

## General

This tab contains mode control, auto-stop and colors.

*   **Mode Control Buttons:** Right from this window, you can immediately activate "Transcription" or "Command" mode. This is useful for quickly testing the program's functionality without returning to the main window.

*   **Automatically stop listening to the microphone via:** This feature helps save resources and prevent accidental recognition by automatically turning off the microphone after a set period of silence.
    *   **How it works:** A timer starts when listening begins. Every recognized word or phrase resets the timer. If you remain silent for longer than the specified duration, listening will stop. This works for both "Transcription" and "Command" modes.
    *   **Available options:** You can choose from several preset intervals (e.g. 10 seconds, 1 minute) or select "Never" to disable this feature.

*   **Transcription Button Color:** Allows you to choose the color that highlights the button in the main window and the tray icon when transcription mode is active.

*   **Command Button Color:** Similarly, allows you to set a unique color to indicate command-listening mode in the main window and tray.

*   **Tray Font Color:** Here you can select the color for the text displayed in the tray icon's tooltip. This is useful for improving readability against different desktop backgrounds.

## System

This tab contains performance, language, file recording, logging and startup options.

*   **Reduce CPU Load:** Recommended for computers with lower performance. This option helps reduce processor resource consumption, which may slightly affect response time but makes the program more stable on less powerful hardware.

*   **Language:** Here you can manually change the application's interface language. Changes take effect immediately.

*   **Record to File:** Enabling this option saves the final transcription results to a text file in the records folder. Use **Open Records Folder** to find them.

*   **Logging Level:** Allows you to choose how much detailed technical information the program will write to its log files. This is useful for diagnosing issues. Different levels are available, from INFO (main events) to DEBUG (maximum detail). Logging to a file must be enabled first.

*   **Start Scribe when I sign in:** Adds or removes Scribe from the current user's startup list. The installer offers the same option, so this checkbox always shows the real state of the operating system. It works for both the installed and the portable build.

Don't forget to click the "Save" button after making changes.
