# Section 13: Troubleshooting and FAQ

**Q: The program won't start or closes immediately.**
**A:** Make sure your antivirus software is not blocking Scribe. Try adding the program's folder to your antivirus exclusion list.

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
**A:** All settings are stored in the `settings.json` file, which is located in the same folder as the program itself.

**Q: How do I reset all settings to default?**
**A:** Close the program, then delete the `settings.json` file. The next time you launch the program, it will create a new file with default settings.

**Q: Does Scribe add punctuation and capital letters?**
**A:** Yes. The **Enable punctuation and capitalization** checkbox on the Models settings page is on by default. Russian and English use a small offline neural model; other languages get basic sentence capitalization. See [Section 14: Punctuation and Capitalization](./14_punctuation.md).

**Q: A short pause splits my sentence and starts a new one.**
**A:** Update to version 1.3.1 or newer. Pauses are now treated as soft boundaries: no period is added and the continuation stays lowercase. Only `?`, `!`, `...`, Enter, or a spoken sentence-ending mark end a sentence.

**Q: How do I dictate a comma, period, or question mark?**
**A:** Create rules on the Replacements tab, for example "comma" -> `[Backspace],` or "question mark" -> `[Backspace]?`. Ready-to-use examples are in [Section 14](./14_punctuation.md#dictating-punctuation-by-voice).

**Q: Does punctuation work without internet?**
**A:** Yes, once the language model has been downloaded. Scribe downloads it automatically on first run into `models/punct/<language>/`. If the model is missing, basic capitalization rules still work offline.

**Q: How do I uninstall the program?**
**A:** The program does not have an installer. To uninstall it, simply delete the folder where you extracted it.

**Q: I found a bug or have a suggestion.**
**A:** Great! Please report it to the developer to help make the program even better.
