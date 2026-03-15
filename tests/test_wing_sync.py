import configparser

import pytest

from wing_sync import _build_osc_get, _get_subnet_broadcasts, _parse_wing_ip, update_config


# --- _parse_wing_ip ---

def test_parse_wing_ip_returns_ip_from_valid_response():
    response = "WING,192.168.1.103,WING-Rack-4AAE,wing-rack,01002NJ0604AAE,3.0.5"
    assert _parse_wing_ip(response) == "192.168.1.103"


def test_parse_wing_ip_returns_none_for_non_wing_response():
    assert _parse_wing_ip("X32,192.168.1.50,XR32") is None


def test_parse_wing_ip_returns_none_for_empty_string():
    assert _parse_wing_ip("") is None


def test_parse_wing_ip_returns_none_for_malformed_response():
    assert _parse_wing_ip("WING") is None


# --- _get_subnet_broadcasts ---

def test_get_subnet_broadcasts_returns_list():
    result = _get_subnet_broadcasts()
    assert isinstance(result, list)


def test_get_subnet_broadcasts_excludes_loopback():
    result = _get_subnet_broadcasts()
    assert "127.0.0.255" not in result


def test_get_subnet_broadcasts_end_in_255():
    for broadcast in _get_subnet_broadcasts():
        assert broadcast.endswith(".255")


def test_get_subnet_broadcasts_returns_at_least_one_entry():
    assert len(_get_subnet_broadcasts()) >= 1


# --- _build_osc_get ---

def test_build_osc_get_result_is_multiple_of_four():
    for address in ["/ch/1/name", "/ch/10/$name", "/ch/40/$name", "/?"]:
        assert len(_build_osc_get(address)) % 4 == 0


def test_build_osc_get_starts_with_address_bytes():
    result = _build_osc_get("/ch/1/name")
    assert result.startswith(b"/ch/1/name")


def test_build_osc_get_padded_with_null_bytes():
    result = _build_osc_get("/ch/1/name")
    assert result[len("/ch/1/name"):] == b"\x00" * (len(result) - len("/ch/1/name"))


def test_build_osc_get_no_type_tag():
    # Must not contain a comma byte (type tag delimiter) anywhere after the address.
    result = _build_osc_get("/ch/1/name")
    assert b"," not in result


def test_build_osc_get_known_value():
    # "/?" is 2 bytes → padded to 4: 2f 3f 00 00
    assert _build_osc_get("/?") == b"/?\x00\x00"


def test_build_osc_get_four_byte_aligned_address_still_gets_null_padding():
    # "/cards/wlive/1/state" is 20 bytes (already a multiple of 4) — must still
    # add 4 null bytes for the OSC null terminator, giving 24 bytes total.
    address = "/cards/wlive/1/state"
    assert len(address) % 4 == 0, "test prerequisite: address must be 4-byte aligned"
    result = _build_osc_get(address)
    assert len(result) == len(address) + 4
    assert result.endswith(b"\x00\x00\x00\x00")


# --- update_config ---

def test_update_config_writes_channel_names(tmp_path):
    config_path = tmp_path / "config.ini"
    config_path.write_text("[Setup]\nmax_num_channels = 32\n")
    update_config(str(config_path), {1: "Kick", 2: "Snare"}, dry_run=False)
    config = configparser.ConfigParser()
    config.read(str(config_path))
    assert config["Channel.Names"]["Ch01"] == "Kick"
    assert config["Channel.Names"]["Ch02"] == "Snare"


def test_update_config_preserves_setup_section(tmp_path):
    config_path = tmp_path / "config.ini"
    config_path.write_text("[Setup]\nmax_num_channels = 32\ninitial_input_directory = C:\\recordings\n")
    update_config(str(config_path), {1: "Kick"}, dry_run=False)
    config = configparser.ConfigParser()
    config.read(str(config_path))
    assert config["Setup"]["max_num_channels"] == "32"
    assert config["Setup"]["initial_input_directory"] == "C:\\recordings"


def test_update_config_replaces_existing_channel_names(tmp_path):
    config_path = tmp_path / "config.ini"
    config_path.write_text("[Setup]\nmax_num_channels = 32\n[Channel.Names]\nCh01 = OldName\nCh05 = AlsoOld\n")
    update_config(str(config_path), {1: "NewName"}, dry_run=False)
    config = configparser.ConfigParser()
    config.read(str(config_path))
    assert config["Channel.Names"]["Ch01"] == "NewName"
    assert "Ch05" not in config["Channel.Names"]


def test_update_config_keys_use_ch_prefix_with_zero_padding(tmp_path):
    config_path = tmp_path / "config.ini"
    config_path.write_text("[Setup]\nmax_num_channels = 32\n")
    update_config(str(config_path), {1: "Kick", 9: "Vocal", 17: "Hat"}, dry_run=False)
    content = config_path.read_text()
    assert "Ch01" in content
    assert "Ch09" in content
    assert "Ch17" in content


def test_update_config_dry_run_does_not_write(tmp_path, capsys):
    config_path = tmp_path / "config.ini"
    config_path.write_text("[Setup]\nmax_num_channels = 32\n")
    update_config(str(config_path), {1: "Kick"}, dry_run=True)
    config = configparser.ConfigParser()
    config.read(str(config_path))
    assert "Channel.Names" not in config


def test_update_config_creates_file_if_not_exists(tmp_path):
    config_path = tmp_path / "new_config.ini"
    assert not config_path.exists()
    update_config(str(config_path), {1: "Kick"}, dry_run=False)
    assert config_path.exists()
    config = configparser.ConfigParser()
    config.read(str(config_path))
    assert config["Channel.Names"]["Ch01"] == "Kick"


def test_update_config_dry_run_prints_names(tmp_path, capsys):
    config_path = tmp_path / "config.ini"
    config_path.write_text("[Setup]\nmax_num_channels = 32\n")
    update_config(str(config_path), {1: "Kick", 2: "Snare"}, dry_run=True)
    output = capsys.readouterr().out
    assert "Ch01" in output
    assert "Kick" in output
    assert "Ch02" in output
    assert "Snare" in output


def test_update_config_writes_wing_ip(tmp_path):
    config_path = tmp_path / "config.ini"
    config_path.write_text("[Setup]\nmax_num_channels = 32\n")
    update_config(str(config_path), {1: "Kick"}, dry_run=False, wing_ip="192.168.1.103")
    config = configparser.ConfigParser()
    config.read(str(config_path))
    assert config["Wing"]["ip"] == "192.168.1.103"


def test_update_config_overwrites_existing_wing_ip(tmp_path):
    config_path = tmp_path / "config.ini"
    config_path.write_text("[Setup]\nmax_num_channels = 32\n[Wing]\nip = 10.0.0.1\n")
    update_config(str(config_path), {1: "Kick"}, dry_run=False, wing_ip="192.168.1.103")
    config = configparser.ConfigParser()
    config.read(str(config_path))
    assert config["Wing"]["ip"] == "192.168.1.103"


def test_update_config_no_wing_section_when_ip_is_none(tmp_path):
    config_path = tmp_path / "config.ini"
    config_path.write_text("[Setup]\nmax_num_channels = 32\n")
    update_config(str(config_path), {1: "Kick"}, dry_run=False, wing_ip=None)
    config = configparser.ConfigParser()
    config.read(str(config_path))
    assert "Wing" not in config


def test_update_config_dry_run_prints_wing_ip(tmp_path, capsys):
    config_path = tmp_path / "config.ini"
    config_path.write_text("[Setup]\nmax_num_channels = 32\n")
    update_config(str(config_path), {1: "Kick"}, dry_run=True, wing_ip="192.168.1.103")
    output = capsys.readouterr().out
    assert "192.168.1.103" in output
