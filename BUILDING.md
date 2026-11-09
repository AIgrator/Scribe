# How to Build Scribe from Source

These steps will guide you through compiling a working `Scribe.exe` application from the source code.

### 1. Prerequisites

*   **Python:** Ensure you have Python 3.10 or newer installed. You can download it from the [official website](https://www.python.org/).
*   **Git:** Required to clone the repository. You can download it from the [official website](https://git-scm.com/).

**For Ubuntu/Debian users:**
Before installing Python dependencies, ensure you have the necessary system libraries:
```bash
sudo apt-get update
sudo apt-get install -y portaudio19-dev libxcb-xinerama0
```

### 2. Clone the Repository

Open a terminal (command prompt) and run the following commands:
```bash
git clone https://github.com/AIgrator/Scribe.git
cd Scribe
```

### 3. Create and Activate a Virtual Environment

This will create an isolated environment for the project.
```bash
# Create the environment
python -m venv venv

# Activate it (for Windows)
.\venv\Scripts\activate

# Activate it (for Linux/macOS)
source venv/bin/activate
```

### 4. Install Dependencies

First, install the required libraries for the application to run:
```bash
pip install -r requirements.txt
```
Next, install PyInstaller, which is used for building the executable:
```bash
pip install pyinstaller
```

### 5. Build the Application

This command will run PyInstaller and build `Scribe.exe`.
```bash
python -m PyInstaller scribe.spec
```

### 6. Build the Installer (Windows only)

The installer is built with [Inno Setup 6](https://jrsoftware.org/isinfo.php). Install it first, then compile the script:

```powershell
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" installer\scribe.iss
```

The version shown by the installer and in Windows is read from `dist\Scribe.exe`, which takes it from `file_version_info.txt`; update that file before a release.

### 7. Result

The build produces these artifacts in the `dist` folder:

*   `dist\Scribe.exe` — standalone/portable executable (add an empty `portable.flag` next to it to keep all data in the same folder);
*   `dist\ScribeSetup.exe` — per-user installer (no administrator rights, installs to `%LOCALAPPDATA%\Programs\Scribe`, data in `%LOCALAPPDATA%\Scribe`).

For a portable release, put `Scribe.exe`, `LICENSE` and an empty `portable.flag` into a folder and zip it as `dist\Scribe-portable.zip`.
