# Myriget

A GUI application designed to help manage and download files from that erista site. This tool helps automate the process of downloading, extracting, and organizing files from myrient links.

## Features

- **Links JSON Generator**
  - Import URLs from a text file
  - Automatically organize links into a structured JSON format
  - Support for both ISO and XBLA games
  - Append new links or replace existing ones

- **Batch Processing**
  - Process files in batches by number or size
  - Configurable batch sizes
  - Progress tracking and status updates

- **Smart File Management**
  - Automatic file downloading
  - Extraction of compressed files
  - Organized file copying to output directory
  - Temporary file cleanup

- **Library Size Calculator**
  - Track total library size
  - Separate tracking for ISO and XBLA games
  - Storage requirement recommendations
  - Missing file information tracking

## Directory Structure

- `config/` - Configuration and links management
- `gui/` - User interface components
- `models/` - Data models and link processing
- `operations/` - Core operations (download, extract, copy)
- `utils/` - Utility functions and logging

## Configuration

The application uses several directories for operation:
- Temporary Download Location (SSD recommended)
- Temporary Extraction Location (SSD recommended)
- Final Output Location (Can be on a slower drive)

## Discussion

For more information and updates, visit the official thread:
[Myriget on Se7enSins](https://www.se7ensins.com/forums/threads/erista-me-companion.1887960/)

## Requirements

See `requirements.txt` in the root directory for required Python packages. 