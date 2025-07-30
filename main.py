import sys
import threading
import os
from dotenv import load_dotenv

# Import modules for TUI and handlers
import src.ui as ui
import src.handlers as handlers

# --- Path Configuration ---
# Add the 'src' directory to sys.path to allow Python to find modules within it.
# This is crucial for importing 'audio_processor.py' when it's in a subdirectory.
# We use os.getcwd() to ensure the path is relative to the current working directory,
# assuming the script is run from the project's root.
try:
    # Construct the absolute path to the 'src' directory based on the current working directory
    src_path = os.path.abspath(os.path.join(os.getcwd(), 'src'))
    # Add the 'src' directory to sys.path if it's not already there
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    
    # Attempt to import audio_processor after modifying sys.path
    import audio_processor
except ModuleNotFoundError:
    print("[red]Error: Could not import 'audio_processor'. Please ensure 'audio_processor.py' is in the 'src' directory and that the script is run from the project's root directory.[/red]")
    sys.exit(1)
except Exception as e:
    print(f"[red]An unexpected error occurred during module import:[/red] {e}")
    sys.exit(1)

# --- Configuration ---
CONFIG_PATH = "config/config.yaml"
CLASSES_PATH = "data/classes.json"
# .env file is assumed to exist for API keys, but we won't create it here directly.
# We'll prompt for it in settings if needed.

# Initialize console here as it's used by multiple handlers and UI functions
from rich.console import Console
console = Console()

def main():
    """Main function to run the TUI."""
    load_dotenv() # Load environment variables from .env file

    # Load config and classes using handlers
    config_data = handlers.load_config_handler(CONFIG_PATH)
    classes_data = handlers.load_classes_handler(CLASSES_PATH)

    if not config_data:
        console.print("[bold red]Failed to load configuration. Exiting.[/bold red]")
        sys.exit(1)

    # Initialize stop event for background thread (not used in current handle_process_recordings)
    stop_event = threading.Event()

    # Load models once at startup
    # The stub load_models() in main.py returns True.
    # If audio_processor.load_models() were to return actual models,
    # they would need to be passed to processing functions.
    loaded_models = audio_processor.load_models() # Modified to call audio_processor and store models
    if not loaded_models: 
        console.print("[bold red]Failed to load AI models. Exiting.[/bold red]")
        sys.exit(1)

    # Ensure directories exist
    incoming_dir = config_data.get("app_settings", {}).get("incoming_audio_dir", "incoming/")
    if not os.path.exists(incoming_dir):
        os.makedirs(incoming_dir, exist_ok=True)
        console.print(f"[bold yellow]Created incoming directory:[/bold yellow] {incoming_dir}")
    
    processed_dir = config_data.get("app_settings", {}).get("processed_recordings_dir", "processed_recordings/")
    if not os.path.exists(processed_dir):
        os.makedirs(processed_dir, exist_ok=True)
        console.print(f"[bold yellow]Created processed recordings directory:[/bold yellow] {processed_dir}")

    # Main application loop
    while True:
        ui.display_main_menu()
        choice = console.input("[bold cyan]Enter your choice (1-6): [/bold cyan]")

        if choice == '1':
            # Call the handler for processing recordings
            handlers.handle_process_recordings(config_data, classes_data, loaded_models, audio_processor)
        elif choice == '2':
            # Call the handler for viewing recordings
            handlers.handle_view_recordings(classes_data, config_data)
        elif choice == '3':
            # Call the handler for managing courses
            classes_data = handlers.handle_manage_courses(classes_data)
        elif choice == '4':
            # Call the handler for adding notes
            handlers.handle_add_notes_to_class(classes_data)
        elif choice == '5':
            # Call the handler for settings
            config_data = handlers.handle_settings(config_data)
        elif choice == '6':
            console.print("[bold magenta]Exiting Academic Recording Organizer. Goodbye![/bold magenta]")
            break
        else:
            console.print("[red]Invalid choice. Please enter a number between 1 and 6.[/red]")
        
        # Clear the console for the next menu display, or handle input for returning to menu
        # console.clear() # This might be too aggressive, let's rely on Panel redraws

if __name__ == "__main__":
    main()
