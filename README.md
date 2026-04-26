# SkillAssessor
# Local Setup Guide

This project can be run locally using Google ADK and a Gemini API key. The steps below cover environment setup, dependency installation, creating a `.env` file, running the app locally.

## Prerequisites

- Python 3.10 or newer
- `pip` installed
- Git installed
- A Google Gemini API key from Google AI Studio

## 1. Clone the project

```bash
git clone <your-repository-url>
cd <your-project-folder>
```

## 2. Create a virtual environment

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Windows (PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

## 3. Install dependencies

```bash
pip install google-adk python-dotenv
```


## 4. Create the `.env` file

### Linux / macOS

```bash
touch multi_tool_agent/.env
```

### Windows (PowerShell)

```powershell
type nul > multi_tool_agent\.env
```
Open the .env file located inside (multi_tool_agent/) and copy-paste the following code.

GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=PASTE_YOUR_ACTUAL_API_KEY_HERE

## 5. Get a Google Gemini API key

1. Open Google AI Studio.
2. Generate an API key.
3. Copy the key.
4. Paste it into the `.env` file.

## 6. Run the application

Using the terminal, navigate to the parent directory of your agent project (e.g. using cd ..):

parent_folder/      <-- navigate to this directory
    multi_tool_agent/
        __init__.py
        agent.py
        .env

Run the following command to launch the UI.

adk web

## 7. Verify the app is working

After the app starts:

- Open the local UI or terminal interface.
- Paste the content of sample.txt in the box
- Confirm that the agent responds without authentication or model errors.

If you get quota or `429 RESOURCE_EXHAUSTED`, wait and retry later or use a project with available quota.

