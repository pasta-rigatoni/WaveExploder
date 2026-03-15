import logging
from configparser import ConfigParser

import pytest

from main import get_channel_num_str, get_channel_name_list, split_multichannel_wav, process_directory, _Summary


PREFIX = "0000"


def channel_names(total, named=None):
    """Build a channel names list. named: {0-based index: name}"""
    names = [""] * total
    if named:
        for idx, name in named.items():
            names[idx] = name
    return names


def make_config(entries):
    config = ConfigParser()
    config["Channel.Names"] = entries
    return config


# --- get_channel_num_str ---

def test_channel_num_str_single_digit_gets_leading_zero():
    assert get_channel_num_str(1) == "Ch01"
    assert get_channel_num_str(9) == "Ch09"


def test_channel_num_str_double_digit_no_leading_zero():
    assert get_channel_num_str(10) == "Ch10"
    assert get_channel_num_str(32) == "Ch32"


# --- get_channel_name_list ---

def test_channel_name_list_returns_named_channels():
    config = make_config({"Ch01": "Kick", "Ch02": "Snare"})
    assert get_channel_name_list(config, "Channel.Names", 2) == ["Kick", "Snare"]


def test_channel_name_list_unnamed_channels_are_empty_string():
    config = make_config({"Ch01": "Kick"})
    assert get_channel_name_list(config, "Channel.Names", 3) == ["Kick", "", ""]


def test_channel_name_list_length_matches_num_channels():
    config = make_config({})
    assert len(get_channel_name_list(config, "Channel.Names", 5)) == 5


# --- split_multichannel_wav ---

def test_split_writes_output_for_named_channels(tmp_path, make_wav):
    make_wav("in/0000_test.wav", num_channels=2, channel_amplitudes={0: 0.5, 1: 0.5})
    out = tmp_path / "out"
    out.mkdir()
    split_multichannel_wav(str(tmp_path / "in"), str(out), PREFIX,
                           False, False, False, True, 0.007,
                           channel_names(2, {0: "Kick", 1: "Snare"}))
    assert (out / "Ch01_Kick.wav").exists()
    assert (out / "Ch02_Snare.wav").exists()


def test_split_skips_unnamed_channel_when_flag_false(tmp_path, make_wav):
    make_wav("in/0000_test.wav", num_channels=2, channel_amplitudes={0: 0.5, 1: 0.5})
    out = tmp_path / "out"
    out.mkdir()
    split_multichannel_wav(str(tmp_path / "in"), str(out), PREFIX,
                           False, False, False, True, 0.007,
                           channel_names(2, {0: "Kick"}))  # Ch02 unnamed
    assert (out / "Ch01_Kick.wav").exists()
    assert not (out / "Ch02_.wav").exists()


def test_split_includes_unnamed_channel_when_flag_true(tmp_path, make_wav):
    make_wav("in/0000_test.wav", num_channels=2, channel_amplitudes={0: 0.5, 1: 0.5})
    out = tmp_path / "out"
    out.mkdir()
    split_multichannel_wav(str(tmp_path / "in"), str(out), PREFIX,
                           False, False, True, True, 0.007,
                           channel_names(2, {0: "Kick"}))  # Ch02 unnamed
    assert (out / "Ch02_.wav").exists()


def test_split_skips_silent_channel_when_flag_false(tmp_path, make_wav):
    make_wav("in/0000_test.wav", num_channels=2, channel_amplitudes={0: 0.5})  # Ch02 silent
    out = tmp_path / "out"
    out.mkdir()
    split_multichannel_wav(str(tmp_path / "in"), str(out), PREFIX,
                           False, False, False, False, 0.007,
                           channel_names(2, {0: "Kick", 1: "Snare"}))
    assert (out / "Ch01_Kick.wav").exists()
    assert not (out / "Ch02_Snare.wav").exists()


def test_split_includes_silent_channel_when_flag_true(tmp_path, make_wav):
    make_wav("in/0000_test.wav", num_channels=2, channel_amplitudes={0: 0.5})  # Ch02 silent
    out = tmp_path / "out"
    out.mkdir()
    split_multichannel_wav(str(tmp_path / "in"), str(out), PREFIX,
                           False, False, False, True, 0.007,
                           channel_names(2, {0: "Kick", 1: "Snare"}))
    assert (out / "Ch02_Snare.wav").exists()


def test_split_output_filename_includes_dir_prefix(tmp_path, make_wav):
    make_wav("MySong/0000_test.wav", num_channels=2, channel_amplitudes={0: 0.5, 1: 0.5})
    out = tmp_path / "out"
    out.mkdir()
    split_multichannel_wav(str(tmp_path / "MySong"), str(out), PREFIX,
                           True, False, False, True, 0.007,
                           channel_names(2, {0: "Kick", 1: "Snare"}))
    assert (out / "MySong_Ch01_Kick.wav").exists()


def test_split_output_filename_excludes_dir_prefix_when_flag_false(tmp_path, make_wav):
    make_wav("MySong/0000_test.wav", num_channels=2, channel_amplitudes={0: 0.5, 1: 0.5})
    out = tmp_path / "out"
    out.mkdir()
    split_multichannel_wav(str(tmp_path / "MySong"), str(out), PREFIX,
                           False, False, False, True, 0.007,
                           channel_names(2, {0: "Kick", 1: "Snare"}))
    assert (out / "Ch01_Kick.wav").exists()
    assert not (out / "MySong_Ch01_Kick.wav").exists()


def test_split_mono_wav_does_not_crash(tmp_path, make_wav):
    make_wav("in/0000_mono.wav", num_channels=1, channel_amplitudes={0: 0.5})
    out = tmp_path / "out"
    out.mkdir()
    split_multichannel_wav(str(tmp_path / "in"), str(out), PREFIX,
                           False, False, False, True, 0.007,
                           channel_names(1, {0: "Mono"}))
    assert (out / "Ch01_Mono.wav").exists()


def test_split_warns_on_channel_count_mismatch(tmp_path, make_wav, caplog):
    make_wav("in/0000_test.wav", num_channels=4, channel_amplitudes={i: 0.5 for i in range(4)})
    out = tmp_path / "out"
    out.mkdir()
    with caplog.at_level(logging.WARNING):
        split_multichannel_wav(str(tmp_path / "in"), str(out), PREFIX,
                               False, False, False, True, 0.007,
                               channel_names(2, {0: "Kick", 1: "Snare"}))
    assert "channels" in caplog.text.lower()


def test_split_prefix_filter_ignores_non_matching_files(tmp_path, make_wav):
    make_wav("in/0000_good.wav", num_channels=2, channel_amplitudes={0: 0.5, 1: 0.5})
    make_wav("in/9999_ignored.wav", num_channels=2, channel_amplitudes={0: 0.5, 1: 0.5})
    out = tmp_path / "out"
    out.mkdir()
    split_multichannel_wav(str(tmp_path / "in"), str(out), PREFIX,
                           False, False, False, True, 0.007,
                           channel_names(2, {0: "Kick", 1: "Snare"}))
    assert len(list(out.iterdir())) == 2  # only from 0000_good.wav


# --- process_directory ---

def test_process_directory_creates_output_directory(tmp_path, make_wav):
    make_wav("in/0000_test.wav", num_channels=2, channel_amplitudes={0: 0.5, 1: 0.5})
    out = tmp_path / "out"  # intentionally not created
    process_directory(str(tmp_path / "in"), str(out), False, PREFIX,
                      False, False, False, True, 0.007,
                      channel_names(2, {0: "Kick", 1: "Snare"}))
    assert (out / "Ch01_Kick.wav").exists()


def test_process_directory_recurse_skips_files_in_root(tmp_path, make_wav):
    make_wav("in/SongA/0000_test.wav", num_channels=2, channel_amplitudes={0: 0.5, 1: 0.5})
    make_wav("in/0000_root.wav", num_channels=2, channel_amplitudes={0: 0.5, 1: 0.5})
    (tmp_path / "out").mkdir()
    process_directory(str(tmp_path / "in"), str(tmp_path / "out"), True, PREFIX,
                      False, False, False, True, 0.007,
                      channel_names(2, {0: "Kick", 1: "Snare"}))
    assert not (tmp_path / "out" / "0000_root.wav").exists()
    assert (tmp_path / "out" / "SongA" / "Ch01_Kick.wav").exists()


def test_process_directory_recurses_multiple_levels(tmp_path, make_wav):
    make_wav("in/Set1/SongA/0000_test.wav", num_channels=2, channel_amplitudes={0: 0.5, 1: 0.5})
    (tmp_path / "out").mkdir()
    process_directory(str(tmp_path / "in"), str(tmp_path / "out"), True, PREFIX,
                      False, False, False, True, 0.007,
                      channel_names(2, {0: "Kick", 1: "Snare"}))
    assert (tmp_path / "out" / "Set1" / "SongA" / "Ch01_Kick.wav").exists()


def test_process_directory_processes_root(tmp_path, make_wav):
    make_wav("in/0000_test.wav", num_channels=2, channel_amplitudes={0: 0.5, 1: 0.5})
    out = tmp_path / "out"
    out.mkdir()
    process_directory(str(tmp_path / "in"), str(out), False, PREFIX,
                      False, False, False, True, 0.007,
                      channel_names(2, {0: "Kick", 1: "Snare"}))
    assert (out / "Ch01_Kick.wav").exists()


def test_process_directory_recurses_into_subdirectories(tmp_path, make_wav):
    make_wav("in/SongA/0000_test.wav", num_channels=2, channel_amplitudes={0: 0.5, 1: 0.5})
    (tmp_path / "out").mkdir()
    process_directory(str(tmp_path / "in"), str(tmp_path / "out"), True, PREFIX,
                      False, False, False, True, 0.007,
                      channel_names(2, {0: "Kick", 1: "Snare"}))
    assert (tmp_path / "out" / "SongA" / "Ch01_Kick.wav").exists()


def test_process_directory_no_recurse_skips_subdirectories(tmp_path, make_wav):
    make_wav("in/SongA/0000_test.wav", num_channels=2, channel_amplitudes={0: 0.5, 1: 0.5})
    (tmp_path / "out").mkdir()
    process_directory(str(tmp_path / "in"), str(tmp_path / "out"), False, PREFIX,
                      False, False, False, True, 0.007,
                      channel_names(2, {0: "Kick", 1: "Snare"}))
    assert not (tmp_path / "out" / "SongA").exists()


# --- use_input_filename_as_output_file_prefix ---

def test_split_output_filename_includes_input_filename_prefix(tmp_path, make_wav):
    make_wav("in/MySong.wav", num_channels=2, channel_amplitudes={0: 0.5, 1: 0.5})
    out = tmp_path / "out"
    out.mkdir()
    split_multichannel_wav(str(tmp_path / "in"), str(out), "",
                           False, True, False, True, 0.007,
                           channel_names(2, {0: "Kick", 1: "Snare"}))
    assert (out / "MySong_Ch01_Kick.wav").exists()
    assert (out / "MySong_Ch02_Snare.wav").exists()


def test_split_input_filename_prefix_takes_priority_over_dir_prefix(tmp_path, make_wav):
    make_wav("MySong/MySong.wav", num_channels=2, channel_amplitudes={0: 0.5, 1: 0.5})
    out = tmp_path / "out"
    out.mkdir()
    split_multichannel_wav(str(tmp_path / "MySong"), str(out), "",
                           True, True, False, True, 0.007,
                           channel_names(2, {0: "Kick", 1: "Snare"}))
    assert (out / "MySong_Ch01_Kick.wav").exists()
    assert not (out / "MySong_MySong_Ch01_Kick.wav").exists()


def test_split_output_filename_excludes_input_filename_prefix_when_flag_false(tmp_path, make_wav):
    make_wav("in/MySong.wav", num_channels=2, channel_amplitudes={0: 0.5, 1: 0.5})
    out = tmp_path / "out"
    out.mkdir()
    split_multichannel_wav(str(tmp_path / "in"), str(out), "",
                           False, False, False, True, 0.007,
                           channel_names(2, {0: "Kick", 1: "Snare"}))
    assert (out / "Ch01_Kick.wav").exists()
    assert not (out / "MySong_Ch01_Kick.wav").exists()


# --- _Summary ---

def test_summary_iadd_accumulates_fields():
    a = _Summary(files=1, written=3, skipped=1)
    b = _Summary(files=2, written=5, skipped=0)
    a += b
    assert a.files == 3
    assert a.written == 8
    assert a.skipped == 1


# --- split_multichannel_wav summary ---

def test_split_summary_counts_written_channels(tmp_path, make_wav):
    make_wav("in/0000_test.wav", num_channels=2, channel_amplitudes={0: 0.5, 1: 0.5})
    out = tmp_path / "out"
    out.mkdir()
    summary = split_multichannel_wav(str(tmp_path / "in"), str(out), PREFIX,
                                     False, False, False, True, 0.007,
                                     channel_names(2, {0: "Kick", 1: "Snare"}))
    assert summary.files == 1
    assert summary.written == 2
    assert summary.skipped == 0


def test_split_summary_counts_skipped_unnamed_channel(tmp_path, make_wav):
    make_wav("in/0000_test.wav", num_channels=2, channel_amplitudes={0: 0.5, 1: 0.5})
    out = tmp_path / "out"
    out.mkdir()
    summary = split_multichannel_wav(str(tmp_path / "in"), str(out), PREFIX,
                                     False, False, False, True, 0.007,
                                     channel_names(2, {0: "Kick"}))  # Ch02 unnamed
    assert summary.written == 1
    assert summary.skipped == 1


def test_split_summary_counts_skipped_silent_channel(tmp_path, make_wav):
    make_wav("in/0000_test.wav", num_channels=2, channel_amplitudes={0: 0.5})  # Ch02 silent
    out = tmp_path / "out"
    out.mkdir()
    summary = split_multichannel_wav(str(tmp_path / "in"), str(out), PREFIX,
                                     False, False, False, False, 0.007,
                                     channel_names(2, {0: "Kick", 1: "Snare"}))
    assert summary.written == 1
    assert summary.skipped == 1


def test_split_summary_counts_multiple_files(tmp_path, make_wav):
    make_wav("in/0000_song1.wav", num_channels=2, channel_amplitudes={0: 0.5, 1: 0.5})
    make_wav("in/0000_song2.wav", num_channels=2, channel_amplitudes={0: 0.5, 1: 0.5})
    out = tmp_path / "out"
    out.mkdir()
    summary = split_multichannel_wav(str(tmp_path / "in"), str(out), PREFIX,
                                     False, False, False, True, 0.007,
                                     channel_names(2, {0: "Kick", 1: "Snare"}))
    assert summary.files == 2
    assert summary.written == 4


def test_split_summary_no_matching_files_returns_zero_counts(tmp_path):
    (tmp_path / "in").mkdir()
    (tmp_path / "out").mkdir()
    summary = split_multichannel_wav(str(tmp_path / "in"), str(tmp_path / "out"), PREFIX,
                                     False, False, False, True, 0.007,
                                     channel_names(2, {0: "Kick", 1: "Snare"}))
    assert summary.files == 0
    assert summary.written == 0
    assert summary.skipped == 0


# --- process_directory summary ---

def test_process_directory_summary_aggregates_subdirectories(tmp_path, make_wav):
    make_wav("in/SongA/0000_test.wav", num_channels=2, channel_amplitudes={0: 0.5, 1: 0.5})
    make_wav("in/SongB/0000_test.wav", num_channels=2, channel_amplitudes={0: 0.5, 1: 0.5})
    summary = process_directory(str(tmp_path / "in"), str(tmp_path / "out"), True, PREFIX,
                                False, False, False, True, 0.007,
                                channel_names(2, {0: "Kick", 1: "Snare"}))
    assert summary.files == 2
    assert summary.written == 4
