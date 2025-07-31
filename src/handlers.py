# src/handlers.py
# Contains the core logic for each TUI menu option.

import sys
import threading
import time
import yaml
import json
import os
import google.generativeai as genai
from dotenv import load_dotenv # Added import

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Assume audio_processor is imported in main.py and passed, or imported here if needed.
# For now, we'll assume it's passed as an argument.

# Define constants that were previously global in main.py
CONFIG_PATH = "config/config.yaml"
CLASSES_PATH = "data/classes.json"

# Initialize console here as it's used by multiple handlers
console = Console()

def load_classes_handler(classes_path):
    """Loads classes data from a JSON file."""
    if not os.path.exists(classes_path):
        console.print(f"[bold yellow]Warning:[/bold yellow] Classes file not found at {classes_path}. Creating a default one.")
        default_classes_data = {"courses": []}
        try:
            with open(classes_path, 'w') as f:
                json.dump(default_classes_data, f, indent=2)
            return default_classes_data
        except Exception as e:
            console.print(f"[bold red]Error creating default classes file:[/bold red] {e}")
            return None
    else:
        try:
            with open(classes_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            console.print(f"[bold red]Error loading classes file:[/bold red] {e}")
            return None

def save_classes_handler(classes_data, classes_path):
    """Saves classes data to a JSON file."""
    try:
        with open(classes_path, 'w') as f:
            json.dump(classes_data, f, indent=2)
        # console.print(f"[green]Classes data saved to {classes_path}[/green]") # Optional: uncomment for verbose logging
        return True
    except Exception as e:
        console.print(f"[bold red]Error saving classes file:[/bold red] {e}")
        return False

def save_config_handler(config_data, config_path):
    """Saves the current config data to config.yaml."""
    try:
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f, indent=2)
    except Exception as e:
        console.print(f"[bold red]Error saving config file:[/bold red] {e}")

# --- Helper functions that were in main.py and are needed by handlers ---
# These should ideally be in their own utility module or passed as arguments.
# For now, defining them here for simplicity, but will refactor to pass them.

def load_config_handler(config_path):
    """Loads configuration from config.yaml and .env."""
    
    # Load API key from .env first
    load_dotenv() # Loads variables from .env file
    gemini_api_key_from_env = os.getenv("GEMINI_API_KEY")
    huggingface_api_key_from_env = os.getenv("HUGGINGFACE_API_KEY") # Load Hugging Face API key from .env

    config_data = {}
    if not os.path.exists(config_path):
        console.print(f"[bold yellow]Warning:[/bold yellow] Configuration file not found at {config_path}. Creating a default one.")
        default_config = {
            "app_settings": {
                "incoming_audio_dir": "incoming/",
                "processed_recordings_dir": "processed_recordings/",
                "gemini_api_key": gemini_api_key_from_env if gemini_api_key_from_env else "YOUR_GEMINI_API_KEY_HERE", # Use key from .env if available
                "huggingface_api_key": huggingface_api_key_from_env if huggingface_api_key_from_env else "YOUR_HUGGINGFACE_API_KEY_HERE" # Use key from .env if available
            },
            "llm_prompts": {
                "summary_prompt": "Summarize the following lecture transcript:",
                "highlights_prompt": "Extract key highlights from the following lecture transcript:"
            }
        }
        try:
            with open(config_path, 'w') as f:
                yaml.dump(default_config, f, indent=2)
            config_data = default_config
        except Exception as e:
            console.print(f"[bold red]Error creating default config file:[/bold red] {e}")
            return None
    else:
        try:
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)
        except Exception as e:
            console.print(f"[bold red]Error loading config file:[/bold red] {e}")
            return None

    # Merge API keys from .env if they exist and config values are placeholders or missing
    if gemini_api_key_from_env:
        if "app_settings" not in config_data:
            config_data["app_settings"] = {}
        if config_data["app_settings"].get("gemini_api_key") == "YOUR_GEMINI_API_KEY_HERE" or not config_data["app_settings"].get("gemini_api_key"):
            config_data["app_settings"]["gemini_api_key"] = gemini_api_key_from_env
            console.print("[green]Gemini API key loaded from .env file.[/green]")

    if huggingface_api_key_from_env:
        if "app_settings" not in config_data:
            config_data["app_settings"] = {}
        if config_data["app_settings"].get("huggingface_api_key") == "YOUR_HUGGINGFACE_API_KEY_HERE" or not config_data["app_settings"].get("huggingface_api_key"):
            config_data["app_settings"]["huggingface_api_key"] = huggingface_api_key_from_env
            console.print("[green]Hugging Face API key loaded from .env file.[/green]")

    # Set default gemini_model if not present
    if "app_settings" in config_data and "gemini_model" not in config_data["app_settings"]:
        config_data["app_settings"]["gemini_model"] = "gemini-2.5-flash-latest"
        save_config_handler(config_data, CONFIG_PATH)

    return config_data

# --- Handler Functions ---

def handle_process_recordings(config_data, classes_data, loaded_models, audio_processor):
    """Handles the 'Process New Recordings' option by processing files in the incoming directory."""
    incoming_dir = config_data.get("app_settings", {}).get("incoming_audio_dir", "incoming/")
    
    if not os.path.exists(incoming_dir):
        os.makedirs(incoming_dir, exist_ok=True)
        console.print(f"[bold yellow]Created incoming directory:[/bold yellow] {incoming_dir}")
        console.print("[yellow]No audio files found to process.[/yellow]")
        return

    console.print(f"\n[bold green]Scanning for new recordings in '{incoming_dir}'...[/bold green]")
    
    files_to_process = [os.path.join(incoming_dir, f) for f in os.listdir(incoming_dir) if f.lower().endswith(('.wav', '.mp3', '.flac', '.ogg'))]
    
    if not files_to_process:
        console.print("[yellow]No audio files found to process in the incoming directory.[/yellow]")
        return

    console.print(f"[bold cyan]Found {len(files_to_process)} audio file(s) to process.[/bold cyan]")

    with Progress(TextColumn("[progress.description]{task.description}"), SpinnerColumn(), transient=True) as progress:
        task_id = progress.add_task("Processing files...", total=len(files_to_process))
        
        for filepath in files_to_process:
            try:
                processed_data = audio_processor.process_audio_file(filepath, config_data, classes_data, loaded_models)
                if processed_data:
                    base_filename = os.path.splitext(os.path.basename(filepath))[0]
                    
                    for class_name, lectures in processed_data.items():
                        class_filename = f"data/{class_name.replace(' ', '_')}.json"
                        
                        # Ensure the class data file exists and load it
                        if os.path.exists(class_filename):
                            with open(class_filename, 'r') as f:
                                class_lectures = json.load(f)
                        else:
                            class_lectures = []
                        
                        # Add new lectures and save
                        class_lectures.extend(lectures)
                        with open(class_filename, 'w') as f:
                            json.dump(class_lectures, f, indent=2)
                        console.print(f"[green]Saved processed data for {class_name} to {class_filename}[/green]")

                    # --- File Archiving Logic ---
                    archive_subdir = os.path.join("archives", base_filename)
                    os.makedirs(archive_subdir, exist_ok=True)

                    # Move original audio file
                    if os.path.exists(filepath):
                        os.rename(filepath, os.path.join(archive_subdir, os.path.basename(filepath)))
                        console.print(f"[green]Archived original audio:[/green] {os.path.basename(filepath)}")

                    # Move SRT file
                    processed_srt_path = os.path.join("processed_recordings", f"{base_filename}.srt")
                    archive_srt_path = os.path.join(archive_subdir, f"{base_filename}.srt") # Define archive path
                    if os.path.exists(processed_srt_path):
                        if not os.path.exists(archive_srt_path): # Check if destination exists
                            os.rename(processed_srt_path, archive_srt_path)
                            console.print(f"[green]Archived SRT file:[/green] {base_filename}.srt")
                        else:
                            console.print(f"[yellow]SRT file already exists in archive, skipping move:[/yellow] {base_filename}.srt")
                else:
                    console.print(f"[red]Failed to process {os.path.basename(filepath)}.[/red]")
            except Exception as e:
                console.print(f"[bold red]Error processing {os.path.basename(filepath)}:[/bold red] {e}")
            
            progress.update(task_id, advance=1)
    
    console.print("\n[bold green]Finished processing audio files.[/bold green]")
    console.print("Press Enter to return to the main menu...")
    input()

def handle_view_recordings(classes_data, config_data):
    """Handles the 'View Processed Recordings' option."""
    console.print("\n[bold blue]Viewing Processed Recordings:[/bold blue]")
    
    data_dir = "data/"
    class_files = [f for f in os.listdir(data_dir) if f.endswith(".json") and f != "classes.json"]

    if not class_files:
        console.print("[yellow]No class recording files found.[/yellow]")
        console.print("Press Enter to return to the main menu...")
        input()
        return

    all_lectures = []
    for filename in class_files:
        filepath = os.path.join(data_dir, filename)
        try:
            with open(filepath, 'r') as f:
                content = json.load(f) # Load the content

                lectures_list = []
                if isinstance(content, list):
                    # If content is already a list of lectures
                    lectures_list = content
                elif isinstance(content, dict) and "lectures" in content and isinstance(content["lectures"], list):
                    # If content is a dict with a "lectures" key containing a list
                    lectures_list = content["lectures"]
                # else: content is not in an expected format, skip or log a warning

                for lecture in lectures_list:
                    # Ensure lecture is a dictionary before appending
                    if isinstance(lecture, dict):
                        all_lectures.append(lecture)
                    else:
                        console.print(f"[yellow]Skipping non-dictionary item in {filename}: {lecture}[/yellow]")

        except Exception as e:
            console.print(f"[red]Error reading class file {filename}: {e}[/red]")

    if not all_lectures:
        console.print("[yellow]No processed recordings found yet. Process some audio files first.[/yellow]")
        console.print("Press Enter to return to the main menu...")
        input()
        return

    table = Table(title="[bold blue]Processed Lectures[/bold blue]")
    table.add_column("ID", style="dim", width=5)
    table.add_column("Course", style="dim", width=20)
    table.add_column("Date", width=12)
    table.add_column("Time", width=10)
    table.add_column("Summary Snippet", width=50)

    for i, record in enumerate(all_lectures):
        table.add_row(
            str(i + 1),
            record.get("metadata", {}).get("course", "Unknown"),
            record.get("metadata", {}).get("date", "N/A"),
            record.get("metadata", {}).get("time", "N/A"),
            record.get("summary", "No summary.")[:50] + "..."
        )

    console.print(table)

    # --- Speaker Labeling - Selection Logic ---
    console.print("\nEnter the ID of the recording to view details or label speakers (or 'b' to go back): ")
    selection = console.input()

    if selection.lower() == 'b':
        return

    try:
        selected_index = int(selection) - 1
        if not (0 <= selected_index < len(all_lectures)):
            console.print("[red]Invalid selection.[/red]")
            return
    except ValueError:
        console.print("[red]Invalid input.[/red]")
        return

    selected_lecture = all_lectures[selected_index]
    class_name = selected_lecture.get("metadata", {}).get("course", "").replace(' ', '_')
    class_filename = f"data/{class_name}.json"

    # --- Speaker Labeling Logic ---
    unique_speakers = selected_lecture.get('speakers', [])
    if not unique_speakers:
        console.print("[yellow]No speaker information found in this recording.[/yellow]")
        console.print("Press Enter to return...")
        input()
        return
        
    console.print("\n[bold blue]Speaker Labeling:[/bold blue]")
    speaker_mapping = {}
    for speaker_id in sorted(unique_speakers):
        new_name = console.input(f"Enter name for '{speaker_id}' (leave blank to keep as is): ")
        if new_name:
            speaker_mapping[speaker_id] = new_name

    if speaker_mapping:
        # Update the lecture data
        for i, segment in enumerate(selected_lecture['transcript_segments']):
            if segment['speaker'] in speaker_mapping:
                selected_lecture['transcript_segments'][i]['speaker'] = speaker_mapping[segment['speaker']]
        
        selected_lecture['speakers'] = list(set(s['speaker'] for s in selected_lecture['transcript_segments']))

        # Save the updated class file
        try:
            with open(class_filename, 'r') as f:
                class_lectures = json.load(f)
            
            # Find and update the specific lecture
            for i, lec in enumerate(class_lectures):
                # A simple check based on summary; a real app would need a unique ID
                if lec['summary'] == selected_lecture['summary']:
                    class_lectures[i] = selected_lecture
                    break
            
            with open(class_filename, 'w') as f:
                json.dump(class_lectures, f, indent=2)
            console.print(f"[green]Speaker labels updated successfully for the selected lecture.[/green]")
        except Exception as e:
            console.print(f"[red]Error saving updated data: {e}[/red]")

    console.print("\nPress Enter to return to the main menu...")
    input()

def handle_add_notes_to_class(classes_data):
    """Handles adding notes to a specific class."""
    console.print("\n[bold blue]Add Notes to Class[/bold blue]")
    
    if not classes_data or not classes_data.get("courses"):
        console.print("[yellow]No courses available. Please add a course first.[/yellow]")
        console.print("Press Enter to return to the main menu...")
        input()
        return

    table = Table(title="[bold blue]Select a Class to Add Notes To[/bold blue]")
    table.add_column("ID", style="dim", width=5)
    table.add_column("Course Name", width=30)

    for i, course in enumerate(classes_data["courses"]):
        table.add_row(str(i + 1), course["name"])
    
    console.print(table)

    while True:
        choice_str = console.input("Enter the ID of the class (or 'b' to go back): ")
        if choice_str.lower() == 'b':
            return
        try:
            choice = int(choice_str)
            if 1 <= choice <= len(classes_data["courses"]):
                selected_course = classes_data["courses"][choice - 1]
                break
            else:
                console.print("[red]Invalid choice.[/red]")
        except ValueError:
            console.print("[red]Invalid input.[/red]")

    class_name = selected_course["name"]
    class_filename = f"data/{class_name.replace(' ', '_')}.json"
    
    console.print(f"\nAdding notes to [bold cyan]{class_name}[/bold cyan]. Type your notes and press Enter twice to save.")
    
    notes = []
    while True:
        line = console.input()
        if not line:
            break
        notes.append(line)
    
    full_note = "\n".join(notes)

    if os.path.exists(class_filename):
        with open(class_filename, 'r+') as f:
            class_data = json.load(f)
            if not isinstance(class_data, list): # Assuming it's a list of lectures
                # If the file is not a list, we might need to decide on a structure.
                # For now, let's assume we add notes to the top-level object if it's a dict.
                if "notes" not in class_data:
                    class_data["notes"] = []
                class_data["notes"].append(full_note)
            else:
                # If it's a list of lectures, where do we add the note?
                # For now, let's create a new structure if we only have a list.
                # This part of the logic might need refinement based on desired JSON structure.
                # Let's assume for now we want to store notes at the top level, so we convert the file structure.
                console.print("[yellow]Note: Adding notes to a class file that is a list of lectures. Converting to a dictionary structure.[/yellow]")
                class_data = {"lectures": class_data, "notes": [full_note]}

            f.seek(0)
            json.dump(class_data, f, indent=2)
            f.truncate()

    else:
        with open(class_filename, 'w') as f:
            json.dump({"lectures": [], "notes": [full_note]}, f, indent=2)

    console.print(f"[green]Notes added successfully to {class_name}.[/green]")
    console.print("Press Enter to return to the main menu...")
    input()

def handle_manage_courses(classes_data):
    """Handles the 'Manage Courses' option."""
    while True:
        console.print("\n[bold blue]Manage Courses[/bold blue]")
        console.print("""
1. View All Courses
2. Add New Course
3. Edit Course
4. Delete Course
5. Back to Main Menu
        """)
        choice = console.input("[bold cyan]Enter your choice (1-5): [/bold cyan]")

        if choice == '1':
            view_all_courses(classes_data)
        elif choice == '2':
            add_course(classes_data)
        elif choice == '3':
            edit_course(classes_data)
        elif choice == '4':
            delete_course(classes_data)
        elif choice == '5':
            break
        else:
            console.print("[red]Invalid choice. Please enter a number between 1 and 5.[/red]")
        
        # Refresh classes_data in case it was modified by add/edit/delete
        # This is a simple way to ensure we're working with the latest data.
        # A more robust approach might involve passing the modified data back.
        classes_data = load_classes_handler(CLASSES_PATH) # Use handler

    return classes_data # Return modified data

def view_all_courses(classes_data):
    """Displays all courses in a table."""
    console.print("\n[bold blue]All Courses[/bold blue]")
    if not classes_data or not classes_data.get("courses"):
        console.print("[italic]No courses defined.[/italic]")
        return

    table = Table(title="[bold blue]Courses[/bold blue]")
    table.add_column("ID", style="dim", width=5)
    table.add_column("Course Name", width=30)
    table.add_column("Keywords", width=40)
    table.add_column("Duration (min)", width=15)
    table.add_column("Schedule", width=40) # Added Schedule column

    for i, course in enumerate(classes_data["courses"]):
        # Format schedule for display
        schedule_info = "No schedule set"
        if "schedule" in course and course["schedule"]:
            schedule_entries = []
            for entry in course["schedule"]:
                days = ", ".join(entry.get("days", []))
                start_time = entry.get("start_time", "N/A")
                schedule_entries.append(f"{days} {start_time}")
            schedule_info = "; ".join(schedule_entries)
        
        table.add_row(
            str(i + 1),
            course["name"],
            ", ".join(course.get("keywords", [])),
            str(course["duration_minutes"]),
            schedule_info # Add schedule info to the row
        )
    console.print(table)
    console.print("Press Enter to return to the Manage Courses menu...")
    input()

def add_course(classes_data):
    """Adds a new course to the classes data."""
    console.print("\n[bold blue]Add New Course[/bold blue]")
    course_name = console.input("Enter course name: ")
    keywords_str = console.input("Enter keywords (comma-separated): ")
    keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]
    
    while True:
        duration_str = console.input("Enter duration in minutes (e.g., 60): ")
        try:
            duration = int(duration_str)
            if duration > 0:
                break
            else:
                console.print("[red]Duration must be a positive number.[/red]")
        except ValueError:
            console.print("[red]Invalid input. Please enter a number for duration.[/red]")

    new_course = {
        "name": course_name,
        "keywords": keywords,
        "duration_minutes": duration
    }
    classes_data["courses"].append(new_course)
    save_classes_handler(classes_data, CLASSES_PATH) # Use handler
    console.print(f"[green]Course '{course_name}' added successfully.[/green]")
    return classes_data # Return modified data

def edit_course(classes_data):
    """Edits an existing course."""
    console.print("\n[bold blue]Edit Course[/bold blue]")
    if not classes_data or not classes_data.get("courses"):
        console.print("[yellow]No courses available to edit.[/yellow]")
        return None # Indicate no change

    table = Table(title="[bold blue]Select Course to Edit[/bold blue]")
    table.add_column("ID", style="dim", width=5)
    table.add_column("Course Name", width=30)
    table.add_column("Keywords", width=40)
    table.add_column("Duration (min)", width=15)

    for i, course in enumerate(classes_data["courses"]):
        table.add_row(
            str(i + 1),
            course["name"],
            ", ".join(course.get("keywords", [])),
            str(course["duration_minutes"])
        )
    console.print(table)

    while True:
        course_id_str = console.input("Enter the ID of the course to edit (or 'b' to go back): ")
        if course_id_str.lower() == 'b':
            return classes_data # Return original data if backing out
        try:
            course_id = int(course_id_str)
            if 1 <= course_id <= len(classes_data["courses"]):
                course_index = course_id - 1
                break
            else:
                console.print("[red]Invalid course ID.[/red]")
        except ValueError:
            console.print("[red]Invalid input. Please enter a number or 'b'.[/red]")

    course = classes_data["courses"][course_index]
    console.print(f"\nEditing course: [bold]{course['name']}[/bold]")

    # --- Edit Basic Course Info ---
    new_name = console.input(f"Enter new course name (current: {course['name']}): ") or course['name']
    
    keywords_str = console.input(f"Enter new keywords (comma-separated, current: {', '.join(course.get('keywords', []))}): ")
    new_keywords = [k.strip() for k in keywords_str.split(',') if k.strip()] if keywords_str else course.get('keywords', [])

    while True:
        duration_str = console.input(f"Enter new duration in minutes (current: {course['duration_minutes']}): ")
        if not duration_str:
            new_duration = course['duration_minutes']
            break
        try:
            new_duration = int(duration_str)
            if new_duration > 0:
                break
            else:
                console.print("[red]Duration must be a positive number.[/red]")
        except ValueError:
            console.print("[red]Invalid input. Please enter a number for duration.[/red]")

    # --- Edit Schedule ---
    current_schedule = course.get("schedule", [])
    console.print("\nCurrent Schedule:")
    if not current_schedule:
        console.print("[italic]No schedule set.[/italic]")
    else:
        for i, entry in enumerate(current_schedule):
            days = ", ".join(entry.get("days", []))
            start_time = entry.get("start_time", "N/A")
            console.print(f"{i + 1}. Days: {days}, Start Time: {start_time}")

    while True:
        console.print("\nSchedule Options:")
        console.print("1. Add new schedule entry")
        if current_schedule: # Only show edit/delete if there are entries
            console.print("2. Edit existing schedule entry")
            console.print("3. Delete schedule entry")
        console.print("4. Done editing schedule")
        
        schedule_choice = console.input("Enter your choice (1-4): ")

        if schedule_choice == '1':
            # Add new schedule entry
            days_str = console.input("Enter days for the new entry (e.g., Monday, Tuesday): ")
            start_time = console.input("Enter start time (e.g., 13:00): ")
            if days_str and start_time:
                new_entry = {
                    "days": [d.strip() for d in days_str.split(',') if d.strip()],
                    "start_time": start_time
                }
                current_schedule.append(new_entry)
                console.print("[green]Schedule entry added.[/green]")
            else:
                console.print("[red]Days and start time are required.[/red]")
        elif schedule_choice == '2':
            # Edit existing schedule entry
            if not current_schedule:
                console.print("[yellow]No schedule entries to edit. Please add an entry first.[/yellow]")
                continue
            
            entry_id_str = console.input("Enter the number of the entry to edit: ")
            try:
                entry_id = int(entry_id_str)
                if 1 <= entry_id <= len(current_schedule):
                    entry_index = entry_id - 1
                    days_str = console.input(f"Enter new days (current: {', '.join(current_schedule[entry_index].get('days', []))}): ")
                    start_time = console.input(f"Enter new start time (current: {current_schedule[entry_index].get('start_time', 'N/A')}): ")
                    
                    if days_str:
                        current_schedule[entry_index]["days"] = [d.strip() for d in days_str.split(',') if d.strip()]
                    if start_time:
                        current_schedule[entry_index]["start_time"] = start_time
                    
                    console.print("[green]Schedule entry updated.[/green]")
                else:
                    console.print("[red]Invalid entry number.[/red]")
            except ValueError:
                console.print("[red]Invalid input. Please enter a number.[/red]")
        elif schedule_choice == '3':
            # Delete schedule entry
            if not current_schedule:
                console.print("[yellow]No schedule entries to delete. Please add an entry first.[/yellow]")
                continue
            
            entry_id_str = console.input("Enter the number of the entry to delete: ")
            try:
                entry_id = int(entry_id_str)
                if 1 <= entry_id <= len(current_schedule):
                    del current_schedule[entry_id - 1]
                    console.print("[green]Schedule entry deleted.[/green]")
                else:
                    console.print("[red]Invalid entry number.[/red]")
            except ValueError:
                console.print("[red]Invalid input. Please enter a number.[/red]")
        elif schedule_choice == '4':
            # Done editing schedule
            break
        else:
            console.print("[red]Invalid choice. Please enter a number between 1 and 4.[/red]")

    # Update the course data with the potentially modified schedule
    classes_data["courses"][course_index]["schedule"] = current_schedule
    
    # Update the course dictionary with new basic info
    classes_data["courses"][course_index]["name"] = new_name
    classes_data["courses"][course_index]["keywords"] = new_keywords
    classes_data["courses"][course_index]["duration_minutes"] = new_duration

    save_classes_handler(classes_data, CLASSES_PATH) # Use handler
    console.print(f"[green]Course '{new_name}' updated successfully.[/green]")
    return classes_data # Return modified data

def _get_gemini_models():
    """Fetches available Gemini models from the API."""
    try:
        # The API key is configured in the main script before this would be called
        models = genai.list_models()
        # Filter for generative models that are relevant for summarization
        return [m.name for m in models if 'generateContent' in m.supported_generation_methods and "gemini" in m.name]
    except Exception as e:
        console.print(f"[bold red]Error fetching Gemini models:[/bold red] {e}")
        return []

def handle_select_gemini_model(config_data):
    """Handles the selection of the Gemini model."""
    console.print("\n[bold blue]Select Gemini Model[/bold blue]")
    
    current_model = config_data.get("app_settings", {}).get("gemini_model", "gemini-2.5-flash-latest")
    console.print(f"Current model: [bold cyan]{current_model}[/bold cyan]")

    available_models = _get_gemini_models()
    
    if not available_models:
        console.print("[yellow]Could not retrieve available models. Please check your API key and internet connection.[/yellow]")
        console.print("Press Enter to return to settings...")
        input()
        return config_data

    # Present only the 2.5 models
    models_to_show = [m for m in available_models if '2.5' in m]
    if not models_to_show:
        # Fallback to showing all models if no 2.5 models are available
        models_to_show = sorted(available_models, reverse=True)[:4]

    console.print("\nSelect a new model:")
    for i, model_name in enumerate(models_to_show):
        console.print(f"{i + 1}. {model_name}")
    
    console.print("0. Back to Settings")

    while True:
        choice_str = console.input("\nEnter your choice: ")
        try:
            choice = int(choice_str)
            if 0 <= choice <= len(models_to_show):
                if choice == 0:
                    return config_data # No change
                
                selected_model = models_to_show[choice - 1]
                config_data["app_settings"]["gemini_model"] = selected_model
                save_config_handler(config_data, CONFIG_PATH)
                console.print(f"[green]Gemini model updated to: [bold]{selected_model}[/bold][/green]")
                console.print("Press Enter to return to settings...")
                input()
                return config_data
            else:
                console.print("[red]Invalid choice. Please select a valid number.[/red]")
        except ValueError:
            console.print("[red]Invalid input. Please enter a number.[/red]")

def delete_course(classes_data):
    """Deletes a course from the classes data."""
    console.print("\n[bold blue]Delete Course[/bold blue]")
    if not classes_data or not classes_data.get("courses"):
        console.print("[yellow]No courses available to delete.[/yellow]")
        return classes_data # Return original data

    table = Table(title="[bold blue]Select Course to Delete[/bold blue]")
    table.add_column("ID", style="dim", width=5)
    table.add_column("Course Name", width=30)
    table.add_column("Keywords", width=40)
    table.add_column("Duration (min)", width=15)

    for i, course in enumerate(classes_data["courses"]):
        table.add_row(
            str(i + 1),
            course["name"],
            ", ".join(course.get("keywords", [])),
            str(course["duration_minutes"])
        )
    console.print(table)

    while True:
        course_id_str = console.input("Enter the ID of the course to delete (or 'b' to go back): ")
        if course_id_str.lower() == 'b':
            return classes_data # Return original data if backing out
        try:
            course_id = int(course_id_str)
            if 1 <= course_id <= len(classes_data["courses"]):
                course_index = course_id - 1
                break
            else:
                console.print("[red]Invalid course ID.[/red]")
        except ValueError:
            console.print("[red]Invalid input. Please enter a number or 'b'.[/red]")

    deleted_course_name = classes_data["courses"][course_index]["name"] # Corrected index variable
    del classes_data["courses"][course_index]
    save_classes_handler(classes_data, CLASSES_PATH) # Use handler
    console.print(f"[green]Course '{deleted_course_name}' deleted successfully.[/green]")
    return classes_data # Return modified data

def handle_settings(config_data):
    """Handles the 'Settings' option."""
    while True:
        console.print("\n[bold blue]Settings[/bold blue]")
        console.print("""
1. View Current Settings
2. Edit Incoming Audio Directory
3. Edit Processed Recordings Directory
4. Update Gemini API Key
5. Select Gemini Model
6. Update Hugging Face API Key
0. Back to Main Menu
        """)
        choice = console.input("[bold cyan]Enter your choice (1-6, 0): [/bold cyan]")

        if choice == '1':
            console.print("\nCurrent Settings:")
            if config_data and "app_settings" in config_data:
                for key, value in config_data["app_settings"].items():
                    console.print(f"- {key}: {value}")
            else:
                console.print("[italic]No settings loaded or available.[/italic]")
            console.print("\nPress Enter to continue...")
            input()
        elif choice == '2':
            new_dir = console.input(f"Enter new incoming audio directory (current: {config_data['app_settings']['incoming_audio_dir']}): ")
            if new_dir:
                config_data['app_settings']['incoming_audio_dir'] = new_dir
                save_config_handler(config_data, CONFIG_PATH)
                console.print(f"[green]Incoming audio directory updated to '{new_dir}'.[/green]")
            else:
                console.print("[yellow]No change made.[/yellow]")
        elif choice == '3':
            new_dir = console.input(f"Enter new processed recordings directory (current: {config_data['app_settings']['processed_recordings_dir']}): ")
            if new_dir:
                config_data['app_settings']['processed_recordings_dir'] = new_dir
                save_config_handler(config_data, CONFIG_PATH)
                console.print(f"[green]Processed recordings directory updated to '{new_dir}'.[/green]")
            else:
                console.print("[yellow]No change made.[/yellow]")
        elif choice == '4':
            console.print("\n[bold yellow]Note:[/bold yellow] It is recommended to store API keys in a .env file for security.")
            console.print("This application currently stores the key in config.yaml for simplicity.")
            api_key = console.input(f"Enter new Gemini API Key (current: {'*' * len(config_data['app_settings']['gemini_api_key']) if config_data['app_settings']['gemini_api_key'] else 'Not Set'}): ")
            if api_key:
                config_data['app_settings']['gemini_api_key'] = api_key
                save_config_handler(config_data, CONFIG_PATH)
                console.print("[green]Gemini API Key updated.[/green]")
            else:
                console.print("[yellow]No change made.[/yellow]")
        elif choice == '5':
            config_data = handle_select_gemini_model(config_data)
        elif choice == '6':
            console.print("\n[bold yellow]Note:[/bold yellow] It is recommended to store API keys in a .env file for security.")
            console.print("This application currently stores the key in config.yaml for simplicity.")
            api_key = console.input(f"Enter new Hugging Face API Key (current: {'*' * len(config_data['app_settings']['huggingface_api_key']) if config_data['app_settings']['huggingface_api_key'] else 'Not Set'}): ")
            if api_key:
                config_data['app_settings']['huggingface_api_key'] = api_key
                save_config_handler(config_data, CONFIG_PATH)
                console.print("[green]Hugging Face API Key updated.[/green]")
            else:
                console.print("[yellow]No change made.[/yellow]")
        elif choice == '0':
            break
        else:
            console.print("[red]Invalid choice. Please enter a number between 1-6 or 0.[/red]")
    
    return config_data # Return modified data
