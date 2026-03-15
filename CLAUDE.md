# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**WaveExploder** splits multi-channel WAV files into individual per-channel WAV files. It's a Python CLI utility for audio engineering workflows (e.g., multi-track live recordings).

## Running Tests

```bash
# Install dependencies
pip install -r requirements.txt

python -m pytest tests/ -v
```

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Run with config.ini defaults
python main.py

# Override input/output directories at the command line
python main.py --input "C:\path\to\recordings" --output "C:\path\to\output"

# Override recursion behaviour (whether to process subdirectories of the input directory)
python main.py --recurse
python main.py --no-recurse

# Use a different config file
python main.py --config other.ini

# Show per-channel RMS values (DEBUG level)
python main.py --verbose
```

`config.ini` is always loaded first; CLI args override individual values when provided. Default log level is INFO; `--verbose` enables DEBUG which adds per-channel RMS output.

## Configuration (`config.ini`)

Two sections control behavior:

**[Setup]** — processing parameters:
- `initial_input_directory` / `initial_output_directory` — source and destination paths (Windows backslash paths)
- `input_file_prefix` — prefix string to filter input files (e.g., `0000`); the code appends `*.wav` automatically
- `max_num_channels` — upper bound of channels to scan (default: 32)
- `recurse_sub_directories` — when True, processes all subdirectories of the input directory recursively, mirroring the folder structure under the output directory
- `use_dir_name_as_output_file_prefix` — prepend the source directory name to output filenames
- `use_input_filename_as_output_file_prefix` — prepend the input WAV filename stem to output filenames; takes priority over `use_dir_name_as_output_file_prefix` when both are True
- `explode_unnamed_channels` / `explode_silent_channels` — whether to extract channels with no name or below the RMS threshold
- `silent_channel_threshold` — RMS value below which a channel is considered silent (default: `0.007`)

**[Channel.Names]** — maps channel numbers to human-readable names:
```ini
Ch09 = Vocal_Lead
Ch17 = Drum_Kick
```
Channels not listed here are considered "unnamed".

## Architecture

The entire application is in `main.py` (~180 lines), with four functions:

1. **`get_channel_num_str(n)`** — formats a channel number as zero-padded string (e.g., `"Ch01"`, `"Ch32"`)
2. **`get_channel_name_list(config, max_channels)`** — builds a name list from the `[Channel.Names]` config section
3. **`split_multichannel_wav(input_dir, output_dir, config)`** — core logic: finds matching WAV files, reads each with `soundfile`, iterates channels, computes RMS via numpy, and writes per-channel WAV files. Output filename format: `[DirName_]ChNN_ChannelName.wav`
4. **`process_directory(input_dir, output_dir, config)`** — walks directories (optionally recursive) and calls `split_multichannel_wav` per directory

**Execution flow:** `config.ini` → settings + channel names → `process_directory` → `split_multichannel_wav` per dir → individual channel WAV files written to output

## Wing Channel Name Sync (`wing_sync.py`)

A companion script that queries a live Behringer Wing mixer via OSC and automatically populates the `[Channel.Names]` section of `config.ini`. Run this once before a session to pull current channel names from the mixer.

```bash
# Query the mixer and update config.ini
python wing_sync.py --ip 192.168.1.103

# Preview what would be written without changing config.ini
python wing_sync.py --ip 192.168.1.103 --dry-run

# Use a different config file
python wing_sync.py --ip 192.168.1.103 --config other.ini
```

**Protocol details:**
- UDP to the Wing's IP on port **2223**
- Sends `/?` first to verify the device is a Wing
- Queries `/ch/{n}/$name` (no args = get request) for channels 1..`max_num_channels`
- Wing responds with the same address and a string argument (max 16 chars)
- Note: `/ch/{n}/$name` is the effective display name shown on the strip. `/ch/{n}/name` is the user-assigned label and was found to always be empty on our mixer.
- Only channels with a non-empty name on the mixer are written to config

**Dependency:** `python-osc` (included in `requirements.txt`)

**Windows Firewall — required one-time setup:**
Windows blocks inbound UDP by default, so the Wing's responses will be silently dropped until you add a firewall rule. Run this once in an elevated (Admin) PowerShell:
```powershell
netsh advfirewall firewall add rule name="WingSync UDP 62000" dir=in action=allow protocol=UDP localport=62000
```

## Key Notes

- **Windows paths**: `config.ini` uses Windows backslash paths (e.g., `C:\Users\...`). The code uses `os.path.join` so it is platform-agnostic, but the config values must match the host OS path format.
- **Code formatter**: Black is configured in the PyCharm project settings.
