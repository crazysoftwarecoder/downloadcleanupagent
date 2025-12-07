# Downloads Folder Cleanup Agent

An AI-powered tool that scans your macOS Downloads folder and suggests which files can be safely deleted using GPT-4o-mini.

## Features

- 🔍 Scans your Downloads folder and collects file metadata
- 🤖 Uses GPT-4o-mini to intelligently analyze files and suggest deletions
- 📊 Provides detailed suggestions with confidence levels and reasoning
- 💾 Saves suggestions to a JSON file for review
- 📌 Remembers files marked as "keep" - files you want to keep won't be suggested again in future runs
- 👀 Option to view/open files before deleting to verify they're safe to remove
- ⚠️ Conservative approach - only suggests files that are likely safe to delete

## Setup

1. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up your OpenAI API key:**
   
   Create a `.env` file in the project root:
   ```bash
   cp .env.example .env
   ```
   
   Then edit `.env` and add your OpenAI API key:
   ```
   OPENAI_API_KEY=sk-your-actual-api-key-here
   ```
   
   You can get your API key from: https://platform.openai.com/api-keys

## Usage

Make sure your virtual environment is activated:
```bash
source venv/bin/activate
```

Then run the script:
```bash
python download_cleanup_agent.py
```

To deactivate the virtual environment when done:
```bash
deactivate
```

The script will:
1. Scan your Downloads folder
2. Filter out files previously marked as "keep"
3. Send file metadata to GPT-4o-mini for analysis
4. Display suggestions organized by confidence level
5. Allow you to select files for deletion and optionally open them for review
6. Save suggestions to `Downloads/cleanup_suggestions.json`
7. Optionally mark files as "keep" so they won't be suggested again

## How It Works

The agent considers several factors when making suggestions:

- **File age**: Old files (6+ months) are often safe to delete
- **File type**: Installers (.dmg, .pkg), temporary files, duplicates
- **File size**: Large files that haven't been accessed recently
- **Naming patterns**: Files with "Copy of", "Untitled", numbered duplicates
- **Conservation**: Keeps recent documents and important file types

## Output

The script provides:
- Summary statistics (total files, suggested deletions, space to free)
- Detailed suggestions grouped by confidence level (high/medium/low)
- Reasoning for each suggestion
- A JSON file with all suggestions for programmatic use

## Safety

⚠️ **Important**: This tool only suggests deletions - it never deletes files automatically. Always review suggestions carefully before deleting anything!

## Requirements

- Python 3.7+
- macOS (for Downloads folder path)
- OpenAI API key with access to GPT-4o-mini

## License

MIT

