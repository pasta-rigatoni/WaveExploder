import argparse
from configparser import ConfigParser
from dataclasses import dataclass
import logging
import sys

import soundfile as sf
import numpy as np
import glob
import os


@dataclass
class _Summary:
    files: int = 0
    written: int = 0
    skipped: int = 0

    def __iadd__(self, other: "_Summary") -> "_Summary":
        self.files += other.files
        self.written += other.written
        self.skipped += other.skipped
        return self

def get_channel_num_str(channel_num : int) -> str:
    """Return a zero-padded channel key string, e.g. 1 -> 'Ch01', 12 -> 'Ch12'.

    Args:
        channel_num: 1-based channel number.
    """

    # Channels have a key (i.e. Ch01, Ch02, Ch19, Ch 12, etc) and a value (i.e. "Drums_Snare" or "Guitar01")
    return_name: str = "Ch"

    # Add a leading zero if the current channel number is less than 10.
    if channel_num < 10:
        return_name += '0'

    # Now put the channel number into the channel config name
    return_name += str(channel_num)

    return return_name


def get_channel_name_list(config_reader : ConfigParser,
                          config_section : str,
                          num_channels : int) -> list[str]:
    """Build a list of channel names from the config, one entry per channel (1..num_channels).

    Channels not present in the config section are returned as empty strings.

    Args:
        config_reader: Parsed ConfigParser instance.
        config_section: Name of the section containing channel name mappings (e.g. 'Channel.Names').
        num_channels: Number of channels to build names for.
    """

    output_list : list[str] = []

    # We want to iterate from 1 to the max number of channels in the wave file.
    # In python a range with a start and end doesn't include the end number in the range, so we have to add one.
    for current_channel_num in range(1, num_channels+1):

        # Get the channel number as a string
        channel_number_str = get_channel_num_str(current_channel_num)

        # Get the name value for this channel
        current_channel_name = config_reader[config_section].get(channel_number_str, "")
        output_list.append(current_channel_name)

    return output_list


def split_multichannel_wav(input_directory : str,
                           output_directory : str,
                           input_file_prefix_filter : str,
                           use_dir_name_as_output_file_prefix : bool,
                           use_input_filename_as_output_file_prefix : bool,
                           explode_unnamed_channels : bool,
                           explode_silent_channels : bool,
                           silent_channel_threshold : float,
                           output_channel_names : list[str]
):
    """Split every matching multi-channel WAV in input_directory into individual per-channel WAV files.

    Scans for files matching '<input_file_prefix_filter>*.wav'. For each file, iterates
    over channels up to len(output_channel_names) and writes a separate WAV file for each
    channel that passes the name and silence filters. Output filenames follow the pattern:
    [<prefix>_]<ChNN>_<channel_name>.wav

    The output prefix is determined by the two prefix flags (use one or neither, not both):
      - use_input_filename_as_output_file_prefix: uses the input WAV filename stem
      - use_dir_name_as_output_file_prefix: uses the input directory name

    Channels beyond len(output_channel_names) are skipped with a warning.

    Args:
        input_directory: Directory to scan for multi-channel WAV files.
        output_directory: Directory where per-channel WAV files are written.
        input_file_prefix_filter: Filename prefix used to filter input files (e.g. '0000');
            '*.wav' is appended automatically. Use empty string to match all WAV files.
        use_dir_name_as_output_file_prefix: If True, prepend the input directory's name
            to each output filename.
        use_input_filename_as_output_file_prefix: If True, prepend the input WAV file's
            stem (filename without extension) to each output filename. Takes priority over
            use_dir_name_as_output_file_prefix if both are True.
        explode_unnamed_channels: If True, extract channels with no name in output_channel_names.
        explode_silent_channels: If True, extract channels whose RMS is below silent_channel_threshold.
        silent_channel_threshold: RMS value below which a channel is considered silent.
        output_channel_names: List of channel names indexed from 0; empty string means unnamed.
    """

    # Get the WAV files matching the input file prefix filter
    wav_file_names_list = glob.glob(os.path.join(input_directory, input_file_prefix_filter + "*.wav"))

    summary = _Summary()

    for current_input_file in wav_file_names_list:

        try:
            data, sample_rate = sf.read(current_input_file)
        except Exception as e:
            logging.warning("Could not read '%s': %s", current_input_file, e)
            continue

        summary.files += 1

        if data.ndim == 1:
            data = data[:, np.newaxis]

        if data.shape[1] > len(output_channel_names):
            logging.warning(
                "'%s' has %d channels but max_num_channels is %d; channels %d-%d will be skipped.",
                current_input_file, data.shape[1], len(output_channel_names),
                len(output_channel_names) + 1, data.shape[1]
            )

        for current_channel_zero_index in range(min(data.shape[1], len(output_channel_names))):

            # First see if we need to actually explode this channel.  We only explode the channels if:
            #
            # - This channel is named OR explode_unnamed_channels is True
            # - This channel is not silent or explode_silent_channels is True
            if explode_unnamed_channels or (output_channel_names[current_channel_zero_index] != ""):

                # Get the channel data for the current channel
                channel_data = data[:, current_channel_zero_index]

                # Get the DB RM value for the complete channel data
                rms = np.sqrt(np.mean(channel_data**2))

                logging.debug("  %s RMS --> %s", get_channel_num_str(current_channel_zero_index + 1), rms)

                # See if we are exploding silent channels and, if not, see if the channel
                # is considered silent.
                if explode_silent_channels or (rms > silent_channel_threshold):

                    #Create the Output File Name
                    output_file_name : str = ""
                    if use_input_filename_as_output_file_prefix:
                        output_file_name += os.path.splitext(os.path.basename(current_input_file))[0] + "_"
                    elif use_dir_name_as_output_file_prefix:
                        output_file_name += os.path.basename(input_directory) + "_"

                    output_file_name += get_channel_num_str(current_channel_zero_index + 1) + \
                                        "_" + \
                                        output_channel_names[current_channel_zero_index] + \
                                        ".wav"

                    sf.write(os.path.join(output_directory, output_file_name), channel_data, sample_rate)
                    summary.written += 1
                else:
                    summary.skipped += 1
            else:
                summary.skipped += 1

    return summary


def process_directory(input_directory : str,
                      output_directory : str,
                      recurse_subdirectories : bool,
                      input_file_prefix_filter : str,
                      use_dir_name_as_output_file_prefix : bool,
                      use_input_filename_as_output_file_prefix : bool,
                      explode_unnamed_channels : bool,
                      explode_silent_channels : bool,
                      silent_channel_threshold : float,
                      output_channel_names : list[str]):
    """Process input_directory and optionally all nested subdirectories.

    Creates output_directory if it does not exist, then calls split_multichannel_wav
    on the directory. If recurse_subdirectories is True, recurses into every
    subdirectory, mirroring the input structure under output_directory.

    Args:
        input_directory: Root directory to process.
        output_directory: Root directory for output files; created if it does not exist.
        recurse_subdirectories: If True, recurse into all subdirectories at any depth.
        input_file_prefix_filter: Passed through to split_multichannel_wav.
        use_dir_name_as_output_file_prefix: Passed through to split_multichannel_wav.
        use_input_filename_as_output_file_prefix: Passed through to split_multichannel_wav.
        explode_unnamed_channels: Passed through to split_multichannel_wav.
        explode_silent_channels: Passed through to split_multichannel_wav.
        silent_channel_threshold: Passed through to split_multichannel_wav.
        output_channel_names: Passed through to split_multichannel_wav.
    """

    os.makedirs(output_directory, exist_ok=True)

    # Convert the wav files in this directory
    logging.info("Processing:  %s", input_directory)
    summary = split_multichannel_wav(input_directory,
                                     output_directory,
                                     input_file_prefix_filter,
                                     use_dir_name_as_output_file_prefix,
                                     use_input_filename_as_output_file_prefix,
                                     explode_unnamed_channels,
                                     explode_silent_channels,
                                     silent_channel_threshold,
                                     output_channel_names)

    if recurse_subdirectories:
        subdirectories = [e for e in os.listdir(input_directory)
                          if os.path.isdir(os.path.join(input_directory, e))]

        for current_input_directory in subdirectories:
            summary += process_directory(
                os.path.join(input_directory, current_input_directory),
                os.path.join(output_directory, current_input_directory),
                recurse_subdirectories,
                input_file_prefix_filter,
                use_dir_name_as_output_file_prefix,
                use_input_filename_as_output_file_prefix,
                explode_unnamed_channels,
                explode_silent_channels,
                silent_channel_threshold,
                output_channel_names
            )

    return summary

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Split a multi-channel WAV into individual per-channel WAV files.")
    parser.add_argument("--config", "-c", default="config.ini", help="Path to config file (default: config.ini)")
    parser.add_argument("--input", "-i", help="Input directory (overrides config)")
    parser.add_argument("--output", "-o", help="Output directory (overrides config)")
    recurse_group = parser.add_mutually_exclusive_group()
    recurse_group.add_argument("--recurse", action="store_true", default=False, help="Recurse into subdirectories (overrides config)")
    recurse_group.add_argument("--no-recurse", action="store_true", default=False, help="Do not recurse into subdirectories (overrides config)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show per-channel RMS values")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s"
    )

    # First read the configuration file and set up our configurable variables
    config : ConfigParser = ConfigParser()

    if not os.path.exists(args.config):
        logging.error("Config file '%s' not found.", args.config)
        sys.exit(1)

    config.read(args.config)

    try:
        config_max_num_channels : int = config["Setup"].getint("max_num_channels")
        config_initial_input_directory :str = args.input or config["Setup"]["initial_input_directory"]
        config_initial_output_directory :str = args.output or config["Setup"]["initial_output_directory"]
        config_recurse_subdirectories: bool = config["Setup"].getboolean("recurse_sub_directories")
        config_input_file_prefix : str = config["Setup"]["input_file_prefix"]
        config_use_dir_name_as_output_file_prefix: bool = config["Setup"].getboolean("use_dir_name_as_output_file_prefix")
        config_use_input_filename_as_output_file_prefix: bool = config["Setup"].getboolean("use_input_filename_as_output_file_prefix")
        config_explode_unnamed_channels : bool = config["Setup"].getboolean("explode_unnamed_channels")
        config_explode_silent_channels : bool = config["Setup"].getboolean("explode_silent_channels")
        config_silent_channel_threshold : float = config["Setup"].getfloat("silent_channel_threshold")
    except KeyError as e:
        logging.error("Missing config key %s.", e)
        sys.exit(1)
    except ValueError as e:
        logging.error("Invalid config value: %s", e)
        sys.exit(1)

    if args.recurse:
        config_recurse_subdirectories = True
    elif args.no_recurse:
        config_recurse_subdirectories = False

    if not os.path.isdir(config_initial_input_directory):
        logging.error("Input directory does not exist: '%s'", config_initial_input_directory)
        sys.exit(1)

    if "Channel.Names" not in config:
        config.add_section("Channel.Names")

    channel_names : list[str] = get_channel_name_list(config,"Channel.Names", config_max_num_channels)

    summary = process_directory(config_initial_input_directory,
                                config_initial_output_directory,
                                config_recurse_subdirectories,
                                config_input_file_prefix,
                                config_use_dir_name_as_output_file_prefix,
                                config_use_input_filename_as_output_file_prefix,
                                config_explode_unnamed_channels,
                                config_explode_silent_channels,
                                config_silent_channel_threshold,
                                channel_names)

    logging.info(
        "** Done — %d file(s) processed, %d channel(s) written, %d skipped **",
        summary.files, summary.written, summary.skipped
    )