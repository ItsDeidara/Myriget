# Myriget

A GUI application designed to help manage and download files from that erista site. This tool helps automate the process of downloading, extracting, and organizing files from myrient links, with support for both ISO and XBLA games.

## Features

- **Links Management**
  - Import URLs from text files
  - Structured JSON storage for links
  - Support for both ISO and XBLA games
  - Append or replace existing links
  - Filter links by type and completion status

- **Batch Processing**
  - Process files in batches by number or size
  - Configurable batch sizes (default 10GB)
  - Real-time progress tracking
  - Status updates and error handling

- **File Operations**
  - Automatic file downloading with progress tracking
  - Extraction of compressed files (7z, zip, rar)
  - Organized file copying to output directory
  - Temporary file cleanup
  - ISO to GOD conversion support

- **Library Management**
  - Track total library size
  - Separate tracking for ISO and XBLA games
  - Storage requirement recommendations
  - Missing file information tracking
  - Automatic directory structure creation

## Directory Structure

- `config/` - Configuration files and links management
  - `links.json` - Stores all game links
  - `settings.json` - Application settings
- `gui/` - User interface components
  - `assets/` - Application icons and resources
- `models/` - Data models and link processing
  - `link.py` - Link management and processing
- `operations/` - Core operations
  - `downloader.py` - File downloading
  - `extractor.py` - File extraction
  - `copier.py` - File copying
  - `iso2god.py` - ISO to GOD conversion
- `utils/` - Utility functions and logging
- `LUA/` - LUA scripts for additional functionality

## Configuration

The application automatically creates and manages several directories:

- `downloads/` - Temporary download location (SSD recommended)
- `temp/` - Temporary extraction location (SSD recommended)
- `output/` - Final output location
  - `god_converted/` - Converted GOD format games
- `logs/` - Application logs and error tracking

Default settings can be configured in `config/settings.json`:
- Batch size (default: 10240 MB)
- Batch mode (By Size/By Number)
- Filter type (Incomplete/All)
- Link type (ISO/XBLA)
- Directory paths

## Requirements

- Python 3.8 or higher
- Required packages (see `requirements.txt`):
  - tkinter (GUI)
  - requests (downloading)
  - py7zr (extraction)
  - tqdm (progress bars)

## Error Handling

The application includes comprehensive error handling:
- Automatic error logging to `logs/error.log`
- GUI error messages for user feedback
- Console fallback for critical errors
- Temporary file cleanup on failure

## Discussion

For more information and updates, visit the official thread:
[Myriget on Se7enSins](https://www.se7ensins.com/forums/threads/erista-me-companion.1887960/) 