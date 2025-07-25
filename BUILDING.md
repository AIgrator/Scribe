# How to Build Scribe from Source

These steps will guide you through compiling a working `Scribe.exe` application from the source code.

### 1. Prerequisites

*   **Python:** Ensure you have Python 3.8 or newer installed. You can download it from the [official website](https://www.python.org/).
*   **Git:** Required to clone the repository. You can download it from the [official website](https://git-scm.com/).

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

### 6. Result

The final `Scribe.exe` file will be located in the `dist` folder.
