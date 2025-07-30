import os
# ADD THIS LINE AT THE TOP OF THE FILE
os.environ['HUGGING_FACE_HUB_CACHE'] = os.path.join(os.getcwd(), 'model_cache')

import time
import json
import warnings
import torch
from dotenv import load_dotenv # Added this line
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.status import Status
from rich.table import Table
from rich.live import Live
import yaml
import json
import os


# Imports for AI models
from whisperx import load_model as load_whisper_model
from pyannote.audio import Pipeline as load_pyannote_pipeline
import google.generativeai as genai

# Suppress specific warnings
warnings.filterwarnings("ignore", category=UserWarning, module='torchaudio')
warnings.filterwarnings("ignore", category=UserWarning, module='pyannote')
warnings.filterwarnings("ignore", category=FutureWarning, module='pyannote')


load_dotenv() # Load environment variables from .env file

console = Console()

# --- Functions for Audio Processing ---

def format_srt_timestamp(seconds: float) -> str:
    """Converts seconds to SRT time format HH:MM:SS,ms"""
    assert seconds >= 0, "non-negative timestamp expected"
    milliseconds = round(seconds * 1000.0)
    hours = int(milliseconds / 3_600_000)
    milliseconds -= hours * 3_600_000
    minutes = int(milliseconds / 60_000)
    milliseconds -= minutes * 60_000
    seconds = int(milliseconds / 1_000)
    milliseconds -= seconds * 1_000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

def write_srt_file(segments: list, filepath: str):
    """Writes transcription segments to an SRT file."""
    with open(filepath, "w", encoding="utf-8") as f:
        for i, segment in enumerate(segments, start=1):
            f.write(f"{i}\n")
            f.write(f"{format_srt_timestamp(segment['start'])} --> {format_srt_timestamp(segment['end'])}\n")
            f.write(f"{segment['text'].strip()}\n\n")



def load_models():
    """
    Loads AI models (WhisperX, pyannote.audio, Gemini) and returns them.
    Requires HF_TOKEN and GEMINI_API_KEY to be set in the .env file.
    """
    console.print("[bold cyan]Loading AI models...[/bold cyan]")
    
    try:
        # Check for CUDA
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Load Hugging Face token
        hf_token = os.getenv("HF_TOKEN")
        if not hf_token:
            console.print("[red]Hugging Face token not found. Please set HF_TOKEN in your .env file.[/red]")
            return False

        # Load Gemini API key
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            console.print("[red]Gemini API key not found. Please set GEMINI_API_KEY in your .env file.[/red]")
            return False

        # Initialize WhisperX model
        console.print("  - Initializing WhisperX model...")
        whisper_model = load_whisper_model(
            "base", 
            device=device, 
            compute_type="float16", 
            download_root="./model_cache"  # Point to the new directory
        )
        console.print("[green]  - WhisperX model initialized.[/green]")

        # Initialize pyannote.audio pipeline
        console.print("  - Initializing pyannote.audio pipeline...")
        # Using a pre-trained diarization model. Requires HF token for access.
        # Removed 'use_auth_token' argument as it caused an error.
        # The token should be automatically picked up from the environment if set.
        diarization_pipeline = load_pyannote_pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1", 
            use_auth_token=hf_token
        )
        console.print("[green]  - pyannote.audio pipeline initialized.[/green]")

        # Initialize Gemini model
        console.print("  - Initializing Gemini model...")
        genai.configure(api_key=gemini_api_key)
        gemini_model = genai.GenerativeModel('gemini-pro')
        console.print("[green]  - Gemini model initialized.[/green]")

        console.print("[bold green]All AI models loaded successfully.[/bold green]")
        return {"whisper": whisper_model, "diarization": diarization_pipeline, "gemini": gemini_model}

    except ImportError as e:
        console.print(f"[red]Import error: {e}. Please ensure all dependencies are installed.[/red]")
        return False
    except Exception as e:
        console.print(f"[red]Error loading AI models:[/red] {e}")
        return False

def process_audio_file(filepath, config_data, classes_data, loaded_models):
    """
    Processes a single audio file using loaded AI models.
    This involves transcription, diarization, segmentation, and AI content generation.
    """
    console.print(f"\n[bold blue]Processing audio file:[/bold blue] {filepath}")
    
    # Use loaded models for transcription and diarization
    transcription_result = transcribe_and_diarize(filepath, loaded_models["whisper"], loaded_models["diarization"])
    if not transcription_result:
        console.print("[red]Failed to transcribe and diarize audio.[/red]")
        return None
    
    # Segment the transcription
    segmented_lectures = segment_audio_by_class(transcription_result, classes_data, filepath) # Modified to pass filepath
    if not segmented_lectures:
        console.print("[red]Failed to segment audio into classes.[/red]")
        return None

    # Generate AI content (summary and highlights) for each lecture
    processed_data = {}
    for class_name, lectures in segmented_lectures.items():
        processed_data[class_name] = []
        for lecture in lectures:
            transcript_text = lecture.get("transcript", "")
            
            if transcript_text:
                summary = generate_ai_content(transcript_text, config_data.get("llm_prompts", {}).get("summary_prompt", "Summarize this:"), loaded_models["gemini"])
                highlights = generate_ai_content(transcript_text, config_data.get("llm_prompts", {}).get("highlights_prompt", "Extract highlights from this:"), loaded_models["gemini"])
                
                lecture_data = {
                    "metadata": lecture.get("metadata", {}),
                    "summary": summary,
                    "highlights": highlights,
                    "speakers": list(set(seg['speaker'] for seg in lecture['segments'])),
                    "transcript_segments": lecture['segments']
                }
                processed_data[class_name].append(lecture_data)
            else:
                console.print(f"[yellow]Skipping AI content generation for empty segment.[/yellow]")

    console.print(f"[green]Audio file processed successfully.[/green]")
    return processed_data

def transcribe_and_diarize(filepath, whisper_model, diarization_pipeline):
    """
    Performs transcription and diarization using loaded models.
    Returns a list of segments with speaker information.
    """
    console.print("  - Performing transcription and diarization...")
    
    try:
        # Step 1: Transcription using WhisperX
        console.print("    - Transcribing audio...")
        result = whisper_model.transcribe(filepath, batch_size=8, language="en")
        transcript_segments = result["segments"]
        console.print("[green]    - Transcription complete.[/green]")

        # Step 2: Save the SRT file
        base_filename = os.path.splitext(os.path.basename(filepath))[0]
        srt_path = os.path.join("processed_recordings", f"{base_filename}.srt")
        write_srt_file(transcript_segments, srt_path)
        console.print(f"[green]    - SRT file saved to: {srt_path}[/green]")

        # Step 3: Diarization using pyannote.audio
        device = "cuda" if torch.cuda.is_available() else "cpu"
        device_color = "green" if device == "cuda" else "red"
        console.print(f"    - Performing diarization with [bold {device_color}]{device.upper()}[/bold {device_color}]...")
        diarization_result = diarization_pipeline(filepath)
        console.print("[green]    - Diarization complete.[/green]")

        # Step 4: Combine transcription and diarization results
        combined_segments = []
        speaker_segments = {}
        for turn, _, speaker in diarization_result.itertracks(yield_label=True):
            if speaker not in speaker_segments:
                speaker_segments[speaker] = []
            speaker_segments[speaker].append({"start": turn.start, "end": turn.end})

        for seg in transcript_segments:
            segment_start = seg["start"]
            segment_end = seg["end"]
            assigned_speaker = "UNKNOWN"
            
            # Find the speaker whose segment overlaps with this transcription segment
            for spk, times in speaker_segments.items():
                for ts in times:
                    if max(segment_start, ts["start"]) < min(segment_end, ts["end"]):
                        assigned_speaker = spk
                        break
                if assigned_speaker != "UNKNOWN":
                    break
            
            combined_segments.append({
                "start": segment_start,
                "end": segment_end,
                "speaker": assigned_speaker,
                "text": seg["text"]
            })
        
        return combined_segments

    except Exception as e:
        console.print(f"[red]Error during transcription/diarization:[/red] {e}")
        return None
    
def segment_audio_by_class(transcription_result, classes_data, audio_filepath): # Added audio_filepath parameter
    """
    Segments the transcription based on filename convention and class schedules.
    """
    console.print("  - Performing segmentation by filename and schedule...")
    
    courses = classes_data.get("courses", [])
    if not courses:
        console.print("[yellow]No courses defined for segmentation. Treating as a single lecture.[/yellow]")
        if transcription_result:
            full_transcript = " ".join([seg["text"] for seg in transcription_result])
            return {
                "Unknown Course": [
                    {
                        "transcript": full_transcript,
                        "segments": transcription_result,
                        "metadata": {
                            "course": "Unknown Course",
                            "date": time.strftime("%Y-%m-%d"),
                            "time": time.strftime("%H:%M:%S"),
                        }
                    }
                ]
            }
        else:
            return {}

    segmented_lectures = {}
    
    # --- Filename Parsing Logic ---
    base_filename = os.path.basename(audio_filepath)
    # Expected format: YYYY-MM-DD_HH-MM-SS_#.mp3
    match = re.match(r"(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})_.*\.mp3", base_filename)
    
    if not match:
        console.print(f"[red]Filename '{base_filename}' does not match expected format (YYYY-MM-DD_HH-MM-SS_#.mp3). Cannot segment by schedule.[/red]")
        # Fallback: treat as a single unknown lecture if transcription exists
        if transcription_result:
            full_transcript = " ".join([seg["text"] for seg in transcription_result])
            return {
                "Unknown Course": [
                    {
                        "transcript": full_transcript,
                        "segments": transcription_result,
                        "metadata": {
                            "course": "Unknown Course",
                            "date": "N/A",
                            "time": "N/A",
                        }
                    }
                ]
            }
        else:
            return {}

    file_date_str, file_time_str = match.groups()
    try:
        file_datetime = datetime.strptime(f"{file_date_str} {file_time_str}", "%Y-%m-%d %H-%M-%S")
        file_day_of_week = file_datetime.strftime("%A") # e.g., "Monday"
        file_time_obj = file_datetime.time()
    except ValueError as e:
        console.print(f"[red]Error parsing date/time from filename '{base_filename}': {e}. Cannot segment by schedule.[/red]")
        # Fallback
        if transcription_result:
            full_transcript = " ".join([seg["text"] for seg in transcription_result])
            return {
                "Unknown Course": [
                    {
                        "transcript": full_transcript,
                        "segments": transcription_result,
                        "metadata": {
                            "course": "Unknown Course",
                            "date": "N/A",
                            "time": "N/A",
                        }
                    }
                ]
            }
        else:
            return {}

    matched_course_name = None
    matched_lecture_data = None

    # --- Schedule Matching Logic ---
    for course in courses:
        for schedule_entry in course.get("schedule", []):
            if file_day_of_week in schedule_entry.get("days", []) and schedule_entry.get("start_time"):
                try:
                    schedule_time_obj = datetime.strptime(schedule_entry["start_time"], "%H:%M").time()
                    # Simple time comparison: if the file's time is close to the schedule's start time
                    # For simplicity, we'll consider it a match if the file's time is within a small window (e.g., 15 mins) of the start time.
                    # A more robust solution might consider duration.
                    time_difference = abs((file_datetime.hour * 60 + file_datetime.minute) - (schedule_time_obj.hour * 60 + schedule_time_obj.minute))
                    
                    if time_difference <= 15: # Within 15 minutes of scheduled start time
                        matched_course_name = course["name"]
                        matched_lecture_data = {
                            "transcript": " ".join([seg["text"] for seg in transcription_result]),
                            "segments": transcription_result,
                            "metadata": {
                                "course": matched_course_name,
                                "date": file_date_str,
                                "time": file_time_str.replace('-', ':'), # Store original time format
                            }
                        }
                        break # Found a match for this course
                except ValueError:
                    console.print(f"[yellow]Warning: Could not parse schedule time '{schedule_entry.get('start_time')}' for course '{course['name']}'.[/yellow]")
        if matched_course_name:
            break # Found a match for any course

    if matched_course_name and matched_lecture_data:
        segmented_lectures[matched_course_name] = [matched_lecture_data]
        console.print(f"[green]  - Segmentation complete. Assigned to course: {matched_course_name}[/green]")
    else:
        console.print("[yellow]No matching course schedule found for the audio file's date/time.[/yellow]")
        # Fallback: treat as a single unknown lecture if transcription exists
        if transcription_result:
            full_transcript = " ".join([seg["text"] for seg in transcription_result])
            segmented_lectures["Unknown Course"] = [
                {
                    "transcript": full_transcript,
                    "segments": transcription_result,
                    "metadata": {
                        "course": "Unknown Course",
                        "date": file_date_str if match else "N/A",
                        "time": file_time_str.replace('-', ':') if match else "N/A",
                    }
                }
            ]
        else:
            return {} # No transcription, no lectures

    return segmented_lectures

def extract_audio_segment(audio_filepath, start_time, end_time, output_filepath):
    """
    Stub function to extract a portion of an audio file.
    Requires pydub and potentially ffmpeg.
    """
    console.print(f"  - Simulating audio extraction from {start_time:.2f}s to {end_time:.2f}s...")
    time.sleep(1) # Simulate processing time
    # In a real implementation:
    # from pydub import AudioSegment
    # audio = AudioSegment.from_file(audio_filepath)
    # segment = audio[start_time*1000:end_time*1000]
    # segment.export(output_filepath, format="wav")
    console.print(f"  - Simulated audio segment saved to: {output_filepath}")
    return output_filepath

def generate_ai_content(text, prompt, gemini_model): # Added gemini_model parameter
    """
    Generates AI content (summary or highlights) using Gemini.
    """
    console.print(f"  - Generating AI content with prompt: '{prompt[:50]}...'")
    
    if not text.strip(): # Handle empty text
        console.print("[yellow]  - Skipping AI content generation for empty text.[/yellow]")
        return "No text provided for AI content generation."

    try:
        # Call the Gemini API
        response = gemini_model.generate_content(f"{prompt}\n\n{text}")
        return response.text
    except Exception as e:
        console.print(f"[red]Error calling Gemini API:[/red] {e}")
        return "AI content generation failed."

# --- Main TUI Integration (will be updated later) ---
# The main.py will call these functions.
# For now, these are just defined here.

if __name__ == "__main__":
    """Main function to run the TUI."""
    load_dotenv() # Load environment variables from .env file

    config_data = load_config()
    classes_data = load_classes()

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


    while True:
        display_main_menu()
        choice = console.input("[bold cyan]Enter your choice (1-5): [/bold cyan]")

        if choice == '1':
            # Call the updated handle_process_recordings, passing loaded_models
            handle_process_recordings(config_data, loaded_models)
        elif choice == '2':
            # Pass config_data to handle_view_recordings
            handle_view_recordings(classes_data, config_data)
        elif choice == '3':
            handle_manage_courses(classes_data)
        elif choice == '4':
            handle_settings(config_data)
        elif choice == '5':
            console.print("[bold magenta]Exiting Academic Recording Organizer. Goodbye![/bold magenta]")
            # In a real app, signal the background thread to stop
            # stop_event.set()
            # if processing_thread and processing_thread.is_alive():
            #     processing_thread.join()
            break
        else:
            console.print("[red]Invalid choice. Please enter a number between 1 and 5.[/red]")
        
        # Clear the console for the next menu display, or handle input for returning to menu
        # console.clear() # This might be too aggressive, let's rely on Panel redraws

if __name__ == "__main__":
    main()
