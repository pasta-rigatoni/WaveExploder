# WaveExploder

[![Tests](https://github.com/pasta-rigatoni/WaveExploder/actions/workflows/tests.yml/badge.svg)](https://github.com/pasta-rigatoni/WaveExploder/actions/workflows/tests.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Splits multi-channel WAV files into individual per-channel WAV files. Built for post-processing multi-track live recordings from a Behringer Wing mixer.

## Scripts

| Script | Purpose |
|---|---|
| `wing_sync.py` | Queries the Wing mixer via OSC and writes channel names to `config.ini` |
| `main.py` | Reads `config.ini` and splits multi-channel WAV files into per-channel files |

Typical workflow: run `wing_sync.py` before a session to pull channel names from the mixer, then run `main.py` after recording to split the files.

## Requirements

- Python 3.10 or newer
- Dependencies:

```bash
pip install -r requirements.txt
```

## Windows Firewall — one-time setup for `wing_sync.py`

Windows blocks inbound UDP by default. Run this once in an elevated (Admin) PowerShell before using `wing_sync.py`:

```powershell
netsh advfirewall firewall add rule name="WingSync UDP 62000" dir=in action=allow protocol=UDP localport=62000
```

## Usage

### `wing_sync.py` — sync channel names from the mixer

```bash
# Auto-discover the Wing on the local network, update config.ini
python wing_sync.py

# Skip discovery, use a known IP
python wing_sync.py --ip 192.168.1.103

# Preview what would be written without changing config.ini
python wing_sync.py --dry-run

# Show raw OSC traffic for debugging
python wing_sync.py --verbose
```

After the first successful run, the Wing's IP address is saved to `config.ini` under `[Wing]`, so subsequent runs skip network discovery automatically.

### `main.py` — split multi-channel WAV files

```bash
# Run with config.ini defaults
python main.py

# Override input/output directories
python main.py --input "C:\path\to\recordings" --output "C:\path\to\output"

# Override recursion behaviour
python main.py --recurse
python main.py --no-recurse

# Use a different config file
python main.py --config other.ini

# Show per-channel RMS values
python main.py --verbose
```

## Configuration (`config.ini`)

Copy `config.ini.example` to `config.ini` and edit it. The file has three sections:

### `[Setup]`

| Key | Description |
|---|---|
| `initial_input_directory` | Root directory to scan for multi-channel WAV files |
| `initial_output_directory` | Directory where per-channel WAV files are written |
| `input_file_prefix` | Filename prefix used to filter input files (e.g. `0000`) |
| `max_num_channels` | Upper bound of channels to scan (default: `32`) |
| `recurse_sub_directories` | If `True`, process all subdirectories recursively |
| `use_dir_name_as_output_file_prefix` | If `True`, prepend the source directory name to output filenames |
| `use_input_filename_as_output_file_prefix` | If `True`, prepend the input WAV filename (without extension) to output filenames; takes priority over `use_dir_name_as_output_file_prefix` |
| `explode_unnamed_channels` | If `True`, extract channels with no name in `[Channel.Names]` |
| `explode_silent_channels` | If `True`, extract channels whose RMS is below the silence threshold |
| `silent_channel_threshold` | RMS value below which a channel is considered silent (default: `0.007`) |

### `[Wing]`

| Key | Description |
|---|---|
| `ip` | IP address of the Wing mixer — written automatically by `wing_sync.py` |

### `[Channel.Names]`

Maps channel numbers to human-readable names. Written automatically by `wing_sync.py`, or set manually:

```ini
[Channel.Names]
Ch09 = Vocal_Lead
Ch17 = Drum_Kick
Ch18 = Drum_Snare
```

Channels not listed here are considered "unnamed". Whether unnamed channels are extracted is controlled by `explode_unnamed_channels` in `[Setup]`.

## Examples

Two typical workflows are supported depending on how recordings are organised on disk.

### Method 1 — one subdirectory per song (Wing SD card layout)

The Wing creates a separate folder for each recording session. Each folder contains a single multi-channel WAV file.

```
Recordings/
├── Song01/
│   └── 0000_Song01.wav   (32-channel)
├── Song02/
│   └── 0000_Song02.wav   (32-channel)
└── Song03/
    └── 0000_Song03.wav   (32-channel)
```

`config.ini`:
```ini
[Setup]
initial_input_directory            = C:\Recordings
initial_output_directory           = C:\Recordings\Exploded
recurse_sub_directories            = True
use_dir_name_as_output_file_prefix = True
use_input_filename_as_output_file_prefix = False
explode_unnamed_channels           = False
explode_silent_channels            = False

[Channel.Names]
Ch09 = Vocal_Lead
Ch17 = Drum_Kick
Ch18 = Drum_Snare
```

Running `python main.py` produces:

```
Exploded/
├── Song01/
│   ├── Song01_Ch09_Vocal_Lead.wav
│   ├── Song01_Ch17_Drum_Kick.wav
│   └── Song01_Ch18_Drum_Snare.wav
├── Song02/
│   ├── Song02_Ch09_Vocal_Lead.wav
│   ├── Song02_Ch17_Drum_Kick.wav
│   └── Song02_Ch18_Drum_Snare.wav
└── Song03/
    ├── Song03_Ch09_Vocal_Lead.wav
    ├── Song03_Ch17_Drum_Kick.wav
    └── Song03_Ch18_Drum_Snare.wav
```

Unnamed channels (e.g. Ch01–Ch08, Ch10–Ch16, Ch19–Ch32) and silent channels are skipped because `explode_unnamed_channels` and `explode_silent_channels` are both `False`.

### Method 2 — flat directory, WAV files named by song

All multi-channel WAV files are in a single directory and are already named by song.

```
Recordings/
├── Song01.wav   (32-channel)
├── Song02.wav   (32-channel)
└── Song03.wav   (32-channel)
```

`config.ini`:
```ini
[Setup]
initial_input_directory            = C:\Recordings
initial_output_directory           = C:\Recordings\Exploded
recurse_sub_directories            = False
input_file_prefix                  =
use_dir_name_as_output_file_prefix = False
use_input_filename_as_output_file_prefix = True
explode_unnamed_channels           = False
explode_silent_channels            = False

[Channel.Names]
Ch09 = Vocal_Lead
Ch17 = Drum_Kick
Ch18 = Drum_Snare
```

Running `python main.py` produces:

```
Exploded/
├── Song01_Ch09_Vocal_Lead.wav
├── Song01_Ch17_Drum_Kick.wav
├── Song01_Ch18_Drum_Snare.wav
├── Song02_Ch09_Vocal_Lead.wav
├── Song02_Ch17_Drum_Kick.wav
├── Song02_Ch18_Drum_Snare.wav
├── Song03_Ch09_Vocal_Lead.wav
├── Song03_Ch17_Drum_Kick.wav
└── Song03_Ch18_Drum_Snare.wav
```

## Output filename format

```
[Prefix_]ChNN_ChannelName.wav
```

The prefix comes from exactly one source (use one or neither, not both):

| Setting | Prefix source | Example |
|---|---|---|
| `use_dir_name_as_output_file_prefix = True` | Source directory name | `Song01_Ch09_Vocal_Lead.wav` |
| `use_input_filename_as_output_file_prefix = True` | Input WAV filename stem | `Song01_Ch09_Vocal_Lead.wav` |
| Both `False` | No prefix | `Ch09_Vocal_Lead.wav` |

## Running tests

```bash
python -m pytest tests/ -v
```

## To Do
<ul>
    <li><b>Behringer X32 Support</b>
        <p>I think it would be pretty easy to add Behringer X32 functionality as well as Behringer Wing, but I no longer have an X32 to test on.</p>
    </li>
</ul>