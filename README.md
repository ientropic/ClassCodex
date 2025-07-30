# Class Codex

Class Codex is a powerful command-line tool designed to process, organize, and analyze your academic audio recordings. It leverages state-of-the-art AI models to transcribe lectures, identify speakers, generate summaries, and extract key highlights, turning your raw audio files into structured, searchable data.

## Overview

The primary goal of Class Codex is to automate the tedious process of managing class recordings. By simply placing your audio files in a designated folder, the application can:

  - Automatically transcribe the entire recording.
  - Distinguish between different speakers in the audio.
  - Generate concise summaries and bullet-point highlights.
  - Intelligently assign the recording to the correct course based on your schedule.
  - Allow you to manage courses, view processed data, and even add your own notes.

All of this is managed through a simple and intuitive text-based user interface (TUI).

## Core Features

  - **Automated Audio Processing**: Processes audio files (`.wav`, `.mp3`, `.flac`, `.ogg`) from an `incoming/` directory.
  - **AI-Powered Transcription**: Uses the WhisperX model for fast and accurate transcription.
  - **Speaker Diarization**: Employs the pyannote.audio pipeline to identify and label different speakers (e.g., `SPEAKER_00`, `SPEAKER_01`).
  - **AI-Generated Content**: Leverages a Google Gemini model to create summaries and highlights from the transcript. The prompts used are fully customizable.
  - **Automatic Course Matching**: Segments recordings and assigns them to courses by matching the audio file's timestamp with defined course schedules.
  - **Course Management**: A dedicated menu to add, edit, and delete your courses and their schedules.
  - **Data Viewing & Speaker Labeling**: View all processed recordings and manually assign real names to the identified speakers (e.g., rename `SPEAKER_00` to "Professor Smith").
  - **Note Taking**: Add and store text-based notes for each class.
  - **Configurable Settings**: Easily change directories and the AI model used for content generation through a settings menu.

## How It Works: The Processing Pipeline

When you choose to "Process New Recordings," Class Codex initiates the following steps:

1.  **Scan**: It looks for new audio files in the `incoming/` directory.
2.  **Transcribe & Diarize**:
      - The audio is first transcribed into text using **WhisperX**.
      - Simultaneously, **pyannote.audio** analyzes the audio to determine who spoke and when.
      - The results are combined, creating a detailed transcript where each line is associated with a speaker label.
      - A standard `.srt` subtitle file is generated.
3.  **Segment by Class**:
      - The application reads the date and time from the audio filename, which must be in **`YYYY-MM-DD_HH-MM-SS_#.mp3`** format.
      - It compares this timestamp to the schedules you've set up in the "Manage Courses" section.
      - If a match is found, the recording is assigned to the corresponding course. Otherwise, it's labeled as "Unknown Course".
4.  **Generate AI Content**:
      - The full transcript is sent to the **Google Gemini** model.
      - Using customizable prompts from `config/config.yaml`, it generates a summary and a list of key highlights.
5.  **Save & Archive**:
      - The data from this process is then appended to a master JSON file for that class (e.g., `data/Year_7_Language_and_Literature.json`).
      - The original audio file and its SRT file are moved to the `archives/` directory to keep the `incoming/` folder clean.

## Getting Started

### 1\. Installation

Clone the repository and install the required Python packages:

```bash
git clone https://github.com/ientropic/ClassCodex.git
cd ClassCodex
pip install -r requirements.txt
```

### 2\. Configuration

Before running the application, you must configure your API keys by creating a `.env` file. This is the only place your secret keys should be stored, as this file is ignored by Git and will not be uploaded to GitHub.

Create a file named `.env` in the root directory of the project and add your keys:

```
GEMINI_API_KEY="YOUR_GOOGLE_AI_STUDIO_API_KEY"
hf_token="YOUR_HUGGING_FACE_API_KEY"
```

The application will automatically load these keys.

### 3\. Running the Application

Launch the application by running `main.py`:

```bash
python main.py
```

This will display the main menu in your terminal.

## Directory Structure

  - `archives/`: Where original audio and SRT files are moved after processing.
  - `config/`: Contains the `config.yaml` settings file.
  - `data/`: Stores JSON files with your course data and processed lecture information.
  - `incoming/`: **Place your new audio recordings here.**
  - `model_cache/`: Caches the downloaded AI models to speed up subsequent runs.
  - `src/`: Contains the Python source code for the application.

## Settings and Configuration (`config/config.yaml`)

You can manage most of these settings directly from the "Settings" menu in the application. Your API keys are managed separately and securely in the `.env` file.

  - **`app_settings`**:

      - `gemini_model`: The specific Gemini model to use (e.g., `gemini-1.5-flash-latest`).
      - `incoming_audio_dir`: The directory to scan for new audio files.
      - `processed_recordings_dir`: The directory where processed outputs are temporarily stored before archival.

  - **`llm_prompts`**:

      - `highlights_prompt`: The prompt used to instruct the AI to extract key points.
      - `summary_prompt`: The prompt used to instruct the AI to generate a summary.

## Planned Functions

  - Advanced audio analysis (e.g., sentiment analysis, topic modeling).
  - Integration with cloud storage (e.g., Google Drive, Dropbox) for audio files.
  - Full-text search capabilities across all processed recordings and notes.
  - A web-based interface for a more graphical experience.
  - Exporting processed data to different formats (e.g., PDF, Word).