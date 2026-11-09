# Section 13: Troubleshooting and FAQ

**Q: The program won't start or closes immediately.**
**A:** Make sure your antivirus software is not blocking Scribe. Try adding the program's folder to your antivirus exclusion list. If the error mentions `KERNEL32.dll` or `GetSystemTimePreciseAsFileTime`, your Windows version is too old — see the next question.

**Q: Does Scribe work on Windows 7?**
**A:** No. Version 1.3.0 and later require **Windows 10 (64-bit) or newer**: offline punctuation and capitalization use ONNX Runtime, which no longer supports Windows 7 or 8.1. The last release that runs on Windows 7 is [v1.2.0](https://github.com/AIgrator/Scribe/releases/tag/v1.2.0) — it works there, but it has no punctuation and capitalization. Current development targets Windows 10 and newer.

**Q: I'm speaking, but nothing is being typed.**
**A:** Check a few things:
1.  Ensure you have activated "Transcription" mode (the button should be highlighted, or you should have pressed the hotkey).
2.  Make sure your cursor is in an active text input field (e.g., a Word document, a browser search bar, or a notepad). The program types where the cursor is.
3.  Verify that the correct microphone is selected in the main window or the tray menu.
4.  Ensure the microphone is not muted and its volume is set to an adequate level in Windows settings.

**Q: The wrong language is being recognized, or it's just a nonsensical string of words.**
**A:** This means the selected model does not match the language you are speaking. Choose the correct model from the dropdown list in the main window or switch to it using a hotkey.

**Q: The hotkeys are not working.**
**A:** The key combination you've chosen might already be in use by another program on your system. Try assigning a different combination in the settings. In rare cases, running the program as an administrator may be required for global hotkeys to work correctly.

**Q: Where are the program settings stored?**
**A:** In `settings.json` inside the Scribe data folder:

*   installed build: `%LOCALAPPDATA%\Scribe\settings.json`;
*   portable build (empty `portable.flag` next to `Scribe.exe`): next to the executable.

The same folder holds `models/`, `records/`, `cache/` and `app.log`. At every start Scribe writes the resolved absolute path to `app.log` as `Data dir: ...`, so the log always shows exactly which folder is in use.

**Q: How do I reset all settings to default?**
**A:** Close the program, then delete `settings.json` from the data folder described above. The next time you launch the program, it will create a new file with default settings.

**Q: Does Scribe add punctuation and capital letters?**
**A:** Yes. The **Enable punctuation and capitalization** checkbox on the Models settings page is on by default. Russian and English use a small offline neural model; other languages get basic sentence capitalization. See [Section 14: Punctuation and Capitalization](./14_punctuation.md).

**Q: A short pause splits my sentence and starts a new one.**
**A:** Update to version 1.3.1 or newer. Pauses are now treated as soft boundaries: no period is added and the continuation stays lowercase. Only `?`, `!`, `...`, Enter, or a spoken sentence-ending mark end a sentence.

**Q: How do I dictate a comma, period, or question mark?**
**A:** Create rules on the Replacements tab, for example "comma" -> `[Backspace],` or "question mark" -> `[Backspace]?`. Ready-to-use examples are in [Section 14](./14_punctuation.md#dictating-punctuation-by-voice).

**Q: Does punctuation work without internet?**
**A:** Yes, once the language model has been downloaded. Scribe downloads it automatically on first run into `models/punct/<language>/` inside the data folder (`%LOCALAPPDATA%\Scribe` for an installed build, next to the executable in portable mode). If the model is missing, basic capitalization rules still work offline.

**Q: How do I uninstall the program?**
**A:** If you used the installer, open **Settings → Apps → Installed apps**, find Scribe and choose **Uninstall**. The uninstaller removes the program and the `%LOCALAPPDATA%\Scribe` data folder; it offers to keep the downloaded voice models (1–2 GB) for a future reinstall. The portable build has no uninstaller: just delete its folder.

**Q: I found a bug or have a suggestion.**
**A:** Great! Please report it to the developer to help make the program even better.
