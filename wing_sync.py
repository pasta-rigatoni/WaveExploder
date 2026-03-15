"""
wing_sync.py — Query a Behringer Wing mixer via OSC and populate the
[Channel.Names] section of config.ini with the names currently set on
the mixer.

Usage:
    python wing_sync.py                        # auto-discover Wing on the local network
    python wing_sync.py --ip 192.168.1.103     # skip discovery, use a known IP
    python wing_sync.py --ip 192.168.1.103 --config other.ini
    python wing_sync.py --ip 192.168.1.103 --dry-run

Windows Firewall — required one-time setup:
    Windows blocks inbound UDP by default, which prevents the Wing's responses
    from reaching this script. Run the following once in an elevated PowerShell:

    netsh advfirewall firewall add rule name="WingSync UDP 62000" dir=in action=allow protocol=UDP localport=62000
"""

import argparse
import configparser
import socket
import sys

from pythonosc.osc_message import OscMessage

WING_OSC_PORT = 2223
LOCAL_PORT = 62000
RESPONSE_TIMEOUT_SEC = 0.25  # seconds to wait per channel query


def _build_osc_get(address: str) -> bytes:
    """Build a bare OSC 'get' message — address only, no type tag.

    The Wing expects bare address-only packets for get requests (no type tag
    string), so we build the raw bytes manually rather than using python-osc,
    which always appends a ',' type tag.
    """
    encoded = address.encode("ascii")
    # Pad to the next 4-byte boundary (OSC string alignment rule).
    total = ((len(encoded) + 4) // 4) * 4
    return encoded + b"\x00" * (total - len(encoded))


def _parse_wing_ip(response_str: str) -> str | None:
    """Extract the IP address from a Wing /? response string.

    The Wing responds with a single comma-separated string:
        WING,<ip>,<console_name>,<model>,<serial>,<firmware>
    Returns the IP field, or None if the string is not a valid Wing response.
    """
    parts = response_str.split(",")
    if len(parts) >= 2 and parts[0] == "WING":
        return parts[1]
    return None


def _send_discovery(sock: socket.socket, ip: str, verbose: bool = False) -> str | None:
    """Send /? to ip and return the Wing's IP from the response, or None on failure."""
    if verbose:
        print(f"  SEND '/?'  raw=2f3f0000  -> {ip}:{WING_OSC_PORT}")
    sock.sendto(b"/?\x00\x00", (ip, WING_OSC_PORT))
    try:
        data, addr = sock.recvfrom(1024)
        if verbose:
            print(f"  RECV from {addr}  raw={data.hex()}")
        msg = OscMessage(data)
        if verbose:
            print(f"       parsed address={msg.address!r}  params={msg.params}")
        if msg.address == "/*" and msg.params:
            return _parse_wing_ip(str(msg.params[0]))
        if verbose:
            print("       not a Wing response — ignoring")
    except socket.timeout:
        if verbose:
            print("  TIMEOUT — no response received")
    except Exception as e:
        if verbose:
            print(f"  ERROR — {e}")
    return None


def _get_subnet_broadcasts() -> list[str]:
    """Return /24 broadcast addresses for all local network interfaces (assumes /24)."""
    try:
        _, _, addresses = socket.gethostbyname_ex(socket.gethostname())
        broadcasts = []
        for ip in addresses:
            if ip == "127.0.0.1":
                continue
            parts = ip.split(".")
            broadcasts.append(".".join(parts[:3] + ["255"]))
        return broadcasts
    except Exception:
        return []


def discover_wing(sock: socket.socket, verbose: bool = False) -> str | None:
    """Broadcast /? on all local interfaces and return the IP of the first Wing that responds."""
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    for broadcast in _get_subnet_broadcasts():
        if verbose:
            print(f"  Trying subnet broadcast {broadcast}...")
        result = _send_discovery(sock, broadcast, verbose=verbose)
        if result:
            return result

    if verbose:
        print("  Trying limited broadcast 255.255.255.255...")
    return _send_discovery(sock, "255.255.255.255", verbose=verbose)


def verify_wing(sock: socket.socket, wing_ip: str, verbose: bool = False) -> bool:
    """Send /? to a specific IP and confirm the response identifies as a Wing."""
    return _send_discovery(sock, wing_ip, verbose=verbose) is not None


def query_channel_names(wing_ip: str | None, max_channels: int, verbose: bool = False) -> tuple[dict[int, str], str]:
    """Query the Wing for channel names 1..max_channels.

    Returns (names, resolved_ip) where names maps channel number to name for
    all channels with a non-empty name on the mixer, and resolved_ip is the
    IP that was actually used (from arg, config, or discovery).
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", LOCAL_PORT))
    sock.settimeout(RESPONSE_TIMEOUT_SEC)

    names: dict[int, str] = {}
    try:
        if wing_ip is None:
            print("No IP specified — broadcasting to discover Wing...")
            wing_ip = discover_wing(sock, verbose=verbose)
            if wing_ip is None:
                print("ERROR: No Wing found on the network — try specifying --ip instead.")
                sys.exit(1)
            print(f"Wing found at {wing_ip}.")
        else:
            print(f"Verifying Wing at {wing_ip}:{WING_OSC_PORT}...")
            if not verify_wing(sock, wing_ip, verbose=verbose):
                print("ERROR: No Wing response to /?  — check the IP address and network connection.")
                sys.exit(1)
            print("Wing confirmed.")
        print("Querying channel names...")

        for n in range(1, max_channels + 1):
            address = f"/ch/{n}/$name"
            msg_bytes = _build_osc_get(address)
            if verbose:
                print(f"  SEND {address!r}  raw={msg_bytes.hex()}")
            sock.sendto(msg_bytes, (wing_ip, WING_OSC_PORT))
            try:
                data, addr = sock.recvfrom(1024)
                if verbose:
                    print(f"  RECV from {addr}  raw={data.hex()}")
                try:
                    msg = OscMessage(data)
                    if verbose:
                        print(f"       parsed address={msg.address!r}  params={msg.params}")
                    if msg.address == address and msg.params:
                        name = str(msg.params[0]).strip().replace(" ", "_")
                        if name:
                            names[n] = name
                except Exception as e:
                    if verbose:
                        print(f"       parse error: {e}")
            except socket.timeout:
                if verbose:
                    print(f"  TIMEOUT for {address}")
    finally:
        sock.close()

    return names, wing_ip


def update_config(config_path: str, names: dict[int, str], dry_run: bool, wing_ip: str | None = None) -> None:
    """Replace the [Channel.Names] section of config_path with the queried names.

    If wing_ip is provided, also writes it to the [Wing] section so future
    runs can skip discovery.
    """
    config = configparser.ConfigParser()
    # Disable key lowercasing so Ch09 is written as Ch09, not ch09.
    config.optionxform = str
    config.read(config_path)

    if wing_ip is not None:
        if not config.has_section("Wing"):
            config.add_section("Wing")
        config.set("Wing", "ip", wing_ip)

    config.remove_section("Channel.Names")
    config.add_section("Channel.Names")
    for n, name in sorted(names.items()):
        config.set("Channel.Names", f"Ch{n:02d}", name)

    if dry_run:
        if wing_ip is not None:
            print(f"[dry-run] Would write Wing IP {wing_ip} to {config_path}.")
        print(f"[dry-run] Would write {len(names)} channel name(s) to {config_path}:")
        for n, name in sorted(names.items()):
            print(f"  Ch{n:02d} = {name}")
        return

    with open(config_path, "w") as f:
        config.write(f)
    print(f"Wrote {len(names)} channel name(s) to {config_path}.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Query a Behringer Wing mixer via OSC and update config.ini channel names."
    )
    parser.add_argument("--ip", default=None, help="IP address of the Wing mixer (omit to auto-discover via broadcast)")
    parser.add_argument(
        "--config", default="config.ini", help="Path to config.ini (default: config.ini)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print discovered names without writing to config.ini",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print raw sent/received bytes and parsed OSC values for each channel query",
    )
    args = parser.parse_args()

    config = configparser.ConfigParser()
    config.read(args.config)
    max_channels = config.getint("Setup", "max_num_channels", fallback=40)

    # IP priority: --ip arg > [Wing] ip in config > auto-discover
    wing_ip = args.ip or config.get("Wing", "ip", fallback=None)

    names, resolved_ip = query_channel_names(wing_ip, max_channels, verbose=args.verbose)

    if not names:
        print("No named channels found on the mixer.")
        sys.exit(0)

    print(f"Found {len(names)} named channel(s).")
    update_config(args.config, names, args.dry_run, wing_ip=resolved_ip)


if __name__ == "__main__":
    main()
