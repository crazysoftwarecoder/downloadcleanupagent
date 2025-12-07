#!/usr/bin/env python3
"""
Downloads Folder Cleanup Agent
Scans the Downloads folder and uses GPT-4o-mini to suggest files for deletion.
"""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv
import questionary

# Load environment variables
load_dotenv()

# Path to the kept files database
KEPT_FILES_DB = Path(__file__).parent / "kept_files.json"


def get_downloads_folder() -> Path:
    """Get the Downloads folder path for macOS."""
    home = Path.home()
    downloads = home / "Downloads"
    if not downloads.exists():
        raise FileNotFoundError(f"Downloads folder not found at {downloads}")
    return downloads


def scan_downloads_folder(downloads_path: Path) -> List[Dict[str, Any]]:
    """Scan the Downloads folder and collect file metadata."""
    files = []
    
    for item in downloads_path.iterdir():
        try:
            stat = item.stat()
            file_info = {
                "name": item.name,
                "path": str(item),
                "size_bytes": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "extension": item.suffix.lower(),
                "modified_date": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "is_file": item.is_file(),
                "is_dir": item.is_dir(),
            }
            files.append(file_info)
        except (OSError, PermissionError) as e:
            print(f"Warning: Could not access {item.name}: {e}")
            continue
    
    return files


def format_files_for_prompt(files: List[Dict[str, Any]]) -> str:
    """Format file list for the AI prompt."""
    # Sort by size (largest first) and then by date (oldest first)
    sorted_files = sorted(files, key=lambda x: (-x["size_bytes"], x["modified_date"]))
    
    formatted = []
    for f in sorted_files:
        item_type = "📁 Folder" if f["is_dir"] else "📄 File"
        formatted.append(
            f"{item_type}: {f['name']} | "
            f"Size: {f['size_mb']} MB | "
            f"Modified: {f['modified_date'][:10]} | "
            f"Extension: {f['extension'] or 'none'}"
        )
    
    return "\n".join(formatted)


def get_deletion_suggestions(files: List[Dict[str, Any]], client: OpenAI) -> Dict[str, Any]:
    """Get deletion suggestions from GPT-4o-mini."""
    
    file_list_text = format_files_for_prompt(files)
    total_size_mb = sum(f["size_mb"] for f in files)
    file_count = len(files)
    
    system_prompt = """You are a helpful assistant that analyzes files in a Downloads folder and suggests which ones can be safely deleted.

Consider these factors when making suggestions:
1. **File age**: Old files (6+ months) are often safe to delete unless they're important documents
2. **File type**: 
   - Old installers (.dmg, .pkg, .exe) are usually safe to delete after installation
   - Duplicate files (same name with numbers like "file (1).pdf")
   - Temporary files (.tmp, .temp, .cache)
   - Old screenshots and images that are likely not needed
3. **File size**: Large files that haven't been accessed recently
4. **Common patterns**: Files with names like "Copy of", "Untitled", or numbered duplicates
5. **Keep**: Recent documents, important file types (.pdf, .docx, .xlsx) that are recent

Return your response as a JSON object with this structure:
{
  "suggestions": [
    {
      "filename": "example.dmg",
      "reason": "Old installer file, likely no longer needed",
      "confidence": "high",
      "size_mb": 150.5,
      "age_days": 180
    }
  ],
  "summary": {
    "total_files_scanned": 50,
    "files_suggested_for_deletion": 10,
    "total_space_to_free_mb": 500.2,
    "keep_recent_days": 30
  }
}

Be conservative - only suggest deletion if you're reasonably confident the file is safe to remove.

Note: The numbers in the example JSON structure above are just examples. You should analyze ALL files and suggest deletion for ALL files that meet the criteria, not limit yourself to any specific number."""

    user_prompt = f"""I have {file_count} items in my Downloads folder, totaling {total_size_mb:.2f} MB.

Here's the list of files and folders:

{file_list_text}

Please analyze these files and suggest which ones can be safely deleted. Return your response as valid JSON only."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3  # Lower temperature for more consistent, conservative suggestions
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON response: {e}")
        print(f"Raw response: {response.choices[0].message.content}")
        raise
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        raise


def display_suggestions(suggestions: Dict[str, Any]):
    """Display the deletion suggestions in a user-friendly format."""
    print("\n" + "="*70)
    print("📋 DELETION SUGGESTIONS")
    print("="*70)
    
    summary = suggestions.get("summary", {})
    print(f"\n📊 Summary:")
    print(f"   • Total files scanned: {summary.get('total_files_scanned', 0)}")
    print(f"   • Files suggested for deletion: {summary.get('files_suggested_for_deletion', 0)}")
    print(f"   • Space to free: {summary.get('total_space_to_free_mb', 0):.2f} MB")
    
    suggestion_list = suggestions.get("suggestions", [])
    if not suggestion_list:
        print("\n✅ No files suggested for deletion. Your Downloads folder looks clean!")
        return
    
    print(f"\n🗑️  Suggested for deletion ({len(suggestion_list)} files):\n")
    
    # Group by confidence level
    high_conf = [s for s in suggestion_list if s.get("confidence", "").lower() == "high"]
    medium_conf = [s for s in suggestion_list if s.get("confidence", "").lower() == "medium"]
    low_conf = [s for s in suggestion_list if s.get("confidence", "").lower() == "low"]
    
    if high_conf:
        print("🔴 HIGH CONFIDENCE:")
        for item in high_conf:
            print(f"   • {item['filename']}")
            print(f"     Reason: {item.get('reason', 'N/A')}")
            print(f"     Size: {item.get('size_mb', 0):.2f} MB")
            if 'age_days' in item:
                print(f"     Age: {item['age_days']} days")
            print()
    
    if medium_conf:
        print("🟡 MEDIUM CONFIDENCE:")
        for item in medium_conf:
            print(f"   • {item['filename']}")
            print(f"     Reason: {item.get('reason', 'N/A')}")
            print(f"     Size: {item.get('size_mb', 0):.2f} MB")
            if 'age_days' in item:
                print(f"     Age: {item['age_days']} days")
            print()
    
    if low_conf:
        print("🟢 LOW CONFIDENCE (review carefully):")
        for item in low_conf:
            print(f"   • {item['filename']}")
            print(f"     Reason: {item.get('reason', 'N/A')}")
            print(f"     Size: {item.get('size_mb', 0):.2f} MB")
            if 'age_days' in item:
                print(f"     Age: {item['age_days']} days")
            print()
    
    print("="*70)
    print("⚠️  Please review these suggestions carefully before deleting any files!")
    print("="*70)


def mark_files_as_keep(suggestions: Dict[str, Any], downloads_path: Path) -> List[str]:
    """Allow user to mark files as 'keep' so they won't be suggested again."""
    suggestion_list = suggestions.get("suggestions", [])
    if not suggestion_list:
        return []
    
    # Create checkbox options with file details
    choices = []
    for item in suggestion_list:
        confidence_emoji = {
            "high": "🔴",
            "medium": "🟡", 
            "low": "🟢"
        }.get(item.get("confidence", "").lower(), "⚪")
        
        # Truncate reason if too long
        reason = item.get('reason', 'N/A')
        if len(reason) > 60:
            reason = reason[:57] + "..."
        
        label = (
            f"{confidence_emoji} {item['filename']} "
            f"({item.get('size_mb', 0):.2f} MB) - {reason}"
        )
        choices.append(questionary.Choice(
            title=label,
            value=item['filename']
        ))
    
    selected = questionary.checkbox(
        "Mark files as 'keep' (they won't be suggested again):",
        choices=choices,
        instruction="(Press <space> to select, <↑↓> to navigate, <enter> to confirm, or <esc> to skip)"
    ).ask()
    
    return selected or []


def interactive_file_selection(suggestions: Dict[str, Any], downloads_path: Path) -> List[str]:
    """Display suggestions with checkboxes and return selected filenames."""
    suggestion_list = suggestions.get("suggestions", [])
    if not suggestion_list:
        return []
    
    # Create checkbox options with file details
    choices = []
    for item in suggestion_list:
        confidence_emoji = {
            "high": "🔴",
            "medium": "🟡", 
            "low": "🟢"
        }.get(item.get("confidence", "").lower(), "⚪")
        
        # Truncate reason if too long
        reason = item.get('reason', 'N/A')
        if len(reason) > 60:
            reason = reason[:57] + "..."
        
        label = (
            f"{confidence_emoji} {item['filename']} "
            f"({item.get('size_mb', 0):.2f} MB) - {reason}"
        )
        choices.append(questionary.Choice(
            title=label,
            value=item['filename']
        ))
    
    selected = questionary.checkbox(
        "Select files to delete (use space to toggle, enter to confirm):",
        choices=choices,
        instruction="(Press <space> to select, <↑↓> to navigate, <enter> to confirm)"
    ).ask()
    
    return selected or []


def load_kept_files() -> set:
    """Load kept files from JSON database and return a set of filenames."""
    if not KEPT_FILES_DB.exists():
        return set()
    
    try:
        with open(KEPT_FILES_DB, "r") as f:
            data = json.load(f)
            kept_filenames = {item["filename"] for item in data.get("kept_files", [])}
            return kept_filenames
    except (json.JSONDecodeError, KeyError, IOError) as e:
        print(f"Warning: Could not load kept files database: {e}")
        return set()


def save_kept_file(filename: str) -> None:
    """Add a file to the kept files database."""
    # Load existing data
    if KEPT_FILES_DB.exists():
        try:
            with open(KEPT_FILES_DB, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            data = {"kept_files": [], "metadata": {}}
    else:
        data = {"kept_files": [], "metadata": {}}
    
    # Check if file is already in the list
    existing_filenames = {item["filename"] for item in data.get("kept_files", [])}
    if filename not in existing_filenames:
        # Add new entry
        kept_entry = {
            "filename": filename,
            "marked_date": datetime.now().isoformat(),
            "reason": "User explicitly marked as keep"
        }
        data["kept_files"].append(kept_entry)
        data["metadata"]["last_updated"] = datetime.now().isoformat()
        
        # Save back to file
        try:
            with open(KEPT_FILES_DB, "w") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save kept file entry: {e}")


def filter_kept_files(files: List[Dict[str, Any]], kept_filenames: set) -> List[Dict[str, Any]]:
    """Remove kept files from the file list before AI analysis."""
    return [f for f in files if f["name"] not in kept_filenames]


def delete_selected_files(selected_filenames: List[str], downloads_path: Path) -> Dict[str, Any]:
    """Delete the selected files and return a summary."""
    deleted = []
    failed = []
    total_freed_mb = 0.0
    
    for filename in selected_filenames:
        file_path = downloads_path / filename
        try:
            if file_path.exists():
                size_mb = file_path.stat().st_size / (1024 * 1024)
                file_path.unlink()  # Delete the file
                deleted.append(filename)
                total_freed_mb += size_mb
            else:
                failed.append(f"{filename} (not found)")
        except Exception as e:
            failed.append(f"{filename} (error: {str(e)})")
    
    return {
        "deleted": deleted,
        "failed": failed,
        "total_freed_mb": total_freed_mb,
        "count": len(deleted)
    }


def run_cleanup_session(client: OpenAI) -> None:
    """Run a single cleanup session."""
    print("🔍 Scanning Downloads folder...")
    downloads_path = get_downloads_folder()
    files = scan_downloads_folder(downloads_path)
    
    if not files:
        print("No files found in Downloads folder.")
        return
    
    print(f"✅ Found {len(files)} items in Downloads folder")
    print(f"📁 Location: {downloads_path}")
    print(f"💾 Total size: {sum(f['size_mb'] for f in files):.2f} MB")
    
    # Load kept files and filter them out
    kept_filenames = load_kept_files()
    if kept_filenames:
        print(f"📌 Filtering out {len(kept_filenames)} file(s) marked as 'keep'")
        files = filter_kept_files(files, kept_filenames)
        print(f"📊 {len(files)} file(s) remaining for analysis\n")
    else:
        print()
    
    print("🤖 Analyzing files with GPT-4o-mini...")
    suggestions = get_deletion_suggestions(files, client)
    
    display_suggestions(suggestions)
    
    # Optionally save suggestions to a file
    output_file = downloads_path / "cleanup_suggestions.json"
    with open(output_file, "w") as f:
        json.dump(suggestions, f, indent=2)
    print(f"\n💾 Suggestions saved to: {output_file}")
    
    # Interactive file selection
    suggestion_list = suggestions.get("suggestions", [])
    if suggestion_list:
        print("\n" + "="*70)
        selected_files = interactive_file_selection(suggestions, downloads_path)
        
        if selected_files:
            # Confirm deletion
            confirm = questionary.confirm(
                f"Are you sure you want to delete {len(selected_files)} file(s)? This cannot be undone!",
                default=False
            ).ask()
            
            if confirm:
                result = delete_selected_files(selected_files, downloads_path)
                print("\n" + "="*70)
                print("🗑️  DELETION RESULTS")
                print("="*70)
                print(f"✅ Successfully deleted: {result['count']} file(s)")
                print(f"💾 Space freed: {result['total_freed_mb']:.2f} MB")
                
                if result['failed']:
                    print(f"\n❌ Failed to delete {len(result['failed'])} file(s):")
                    for failure in result['failed']:
                        print(f"   • {failure}")
                print("="*70)
            else:
                print("\n❌ Deletion cancelled.")
        else:
            print("\nℹ️  No files selected for deletion.")
        
        # Ask if user wants to mark any files as "keep"
        keep_files = mark_files_as_keep(suggestions, downloads_path)
        if keep_files:
            for filename in keep_files:
                save_kept_file(filename)
            print(f"\n✅ Marked {len(keep_files)} file(s) as keep. They won't be suggested in future runs.")


def main():
    """Main function to run the cleanup agent."""
    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not found in environment variables.")
        print("Please set it in your .env file or export it as an environment variable.")
        return
    
    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)
    
    # Main loop
    while True:
        try:
            run_cleanup_session(client)
        except Exception as e:
            print(f"Error: {e}")
            raise
        
        # Ask if user wants to run again
        print("\n" + "="*70)
        run_again = questionary.select(
            "What would you like to do?",
            choices=[
                questionary.Choice("Run cleanup again", value=True),
                questionary.Choice("Exit", value=False)
            ]
        ).ask()
        
        if not run_again:
            print("\n👋 Goodbye!")
            break
        print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()

