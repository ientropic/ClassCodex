# TUI Implementation Summary: Academic Recording Organizer App

This document outlines the design, current status, and future plans for the Terminal User Interface (TUI) of the Academic Recording Organizer App. The application leverages AI models to process audio lectures, providing transcriptions, speaker diarization, and AI-generated summaries and highlights.

## 1. Project Overview

The Academic Recording Organizer App is designed to streamline the process of managing and extracting information from audio lectures. It automates tasks such as transcription, speaker identification, and content summarization using advanced AI models. The application provides an interactive TUI for user control and configuration.

***

## 2. Key Components and Technical Details

The application is structured into several key Python modules, each serving a distinct purpose:

*   **`main.py` (Orchestrator):**
    *   **Role:** The application's entry point. It initializes the environment, loads configurations and AI models, ensures necessary directories exist, and manages the main application loop. It orchestrates interactions between the UI and handler modules based on user input.
    *   **Technical Details:** Uses `dotenv` to load environment variables (API keys), `rich.console.Console` for output, and imports modules from `src/`. It calls `audio_processor.load_models()` to prepare AI models for use.

*   **`src/ui.py` (View):**
    *   **Role:** Responsible for all visual output to the terminal. It defines the structure and content of menus, tables, and other interactive elements presented to the user.
    *   **Technical Details:** Heavily relies on the `rich` library for creating a visually appealing and informative TUI experience, including styled text, tables, and progress indicators. (Specific implementation details are managed within this module).

*   **`src/handlers.py` (Controller):**
    *   **Role:** Implements the core business logic for each user-selectable option in the TUI. It acts as the intermediary between the UI and the underlying processing logic in `audio_processor.py`.
    *   **Technical Details:** Handles file operations for configuration (`config.yaml`) and course data (`data/classes.json`). It orchestrates the processing of audio files by calling functions in `audio_processor.py`, manages course data (CRUD operations), and handles application settings. It also incorporates speaker labeling logic for processed recordings.

*   **`src/audio_processor.py` (Core AI Logic):**
    *   **Role:** This module contains the heart of the AI-powered audio processing. It manages the loading of AI models and performs the core tasks of transcription, diarization, segmentation, and AI content generation.
    *   **Technical Details:**
        *   **Transcription:** Integrates **WhisperX** (`whisperx.load_model`) for accurate speech-to-text conversion.
        *   **Speaker Diarization:** Utilizes **pyannote.audio** (`pyannote.audio.Pipeline`) to identify different speakers within the audio.
        *   **AI Content Generation:** Leverages **Google Generative AI (Gemini Pro)** (`google.generativeai`) to create summaries and extract highlights from transcribed segments, using prompts defined in `config.yaml`.
        *   **Segmentation:** Implements logic to segment audio based on identified courses (using keywords) and speaker changes.
        *   **Output:** Generates SRT files for timestamps and JSON files containing processed data (transcripts, summaries, highlights, speaker labels).

*   **Configuration and Data Management:**
    *   **`config/config.yaml`:** Stores application settings such as input/output directory paths and LLM prompts for summarization and highlights.
    *   **`.env`:** Securely stores sensitive API keys (Gemini API Key, Hugging Face API Key). The application loads these keys from this file.
    *   **`data/classes.json`:** Manages course-specific data, including course names, associated keywords for segmentation, and expected duration.
    *   **`processed_recordings/`:** Directory where generated SRT and JSON files are stored.
    *   **`archives/`:** Used to store original audio files and their processed outputs after successful processing.

## 3. Key Technologies Used

*   **Programming Language:** Python
*   **TUI Framework:** `rich` library for enhanced terminal output (colors, panels, tables, progress bars, spinners).
*   **AI Models & Libraries:**
    *   WhisperX (for transcription)
    *   pyannote.audio (for speaker diarization)
    *   Google Generative AI (Gemini Pro, for summarization and highlights)
*   **Configuration Management:** `PyYAML` for `config.yaml`, `python-dotenv` for `.env` file handling.

## 4. Application Workflow

1.  **Input:** Audio files (e.g., `.wav`, `.mp3`) are placed into the `incoming/` directory.
2.  **Execution:** The user runs the application via `main.py` and selects "Process New Recordings" from the TUI.
3.  **Processing:**
    *   The app scans the `incoming/` directory for audio files.
    *   For each file, `src/audio_processor.py` is invoked to:
        *   Load necessary AI models (WhisperX, pyannote.audio, Gemini).
        *   Transcribe the audio.
        *   Perform speaker diarization.
        *   Segment the audio based on course keywords and speaker changes.
        *   Generate summaries and highlights using Gemini.
    *   Visual feedback (spinners, progress bars) is provided via `rich`.
4.  **Output:** Processed data (transcripts, summaries, highlights, speaker labels) is saved as JSON files, and timestamped transcriptions are saved as SRT files in the `processed_recordings/` directory.
5.  **Archiving:** Original audio files and their corresponding processed outputs are moved to the `archives/` directory.
6.  **User Interaction:** Users can view processed recordings, manage course data, and adjust application settings through the TUI.

## 5. Implemented Features

*   **Batch Audio Processing:** Processes all audio files in the `incoming/` directory.
*   **AI-Powered Analysis:** Includes transcription, speaker diarization, and LLM-based summarization/highlight generation.
*   **SRT File Generation:** Creates timestamped subtitle files.
*   **Visual Feedback:** Utilizes `rich` for spinners, progress bars, tables, and styled output.
*   **Processed Recordings View:** Displays a table of processed lectures with summary snippets.
*   **Interactive Speaker Labeling:** Allows users to assign custom names to identified speakers.
*   **Course Management:** Full CRUD (Create, Read, Update, Delete) functionality for courses, including keywords for segmentation.
*   **Settings Management:** Allows configuration of directories and API keys (loaded from `.env`).

## 6. Unimplemented Features / Future Enhancements

*   **Audio Segment Extraction:** The `extract_audio_segment` function in `src/audio_processor.py` is currently a stub and requires full implementation (e.g., using `pydub`).
*   **Background Processing:** Code for a background processing thread is present but commented out, indicating a planned feature for non-blocking processing that needs full integration.
*   **On-Demand Custom Reporting:** A feature to generate specific reports based on user-defined criteria (date ranges, keywords, courses) is planned but not yet implemented.
*   **Automatic Course Report Generation:** While mentioned, the mechanism for automatically generating and updating `.md` reports that synthesize summaries across multiple lectures for a course needs to be fully developed.
*   **Detailed `src/ui.py` Features:** The specific interactive elements and functionalities within `src/ui.py` beyond what's handled by `handlers.py` are not fully detailed here.
*   **Enhanced Error Handling:** Further refinement of error handling across all modules to cover more edge cases and provide more user-friendly error messages.
*   **Support for More Audio Formats:** Currently supports `.wav`, `.mp3`, `.flac`, `.ogg`. Expanding this list could be beneficial.

***

*Notes for later:*
*   `classes.json` should ideally include a start time for each lecture, possibly in a 24-hour clock format, to aid in chronological ordering or reporting.
