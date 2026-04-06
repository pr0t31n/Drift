#!/usr/bin/env python3
"""
drift.py — Wireless Reconnect Client
=====================================
Installed on a device already connected to the target wireless network.
Periodically disconnects and reconnects to the network to generate
deauthentication and re-association traffic — used to trigger and test
wireless misconfiguration vulnerabilities (e.g. PMKID capture, KRACK
retransmission windows, WPA-Enterprise credential replay).

Usage:
  python3 drift.py --ssid <SSID> [options]
  python3 drift.py --ssid "CorpWifi" --interval 60 --jitter 15 --interface wlan0

Options:
  --ssid       SSID of the target network (required)
  --interface  Wireless interface (default: auto-detected)
  --interval   Seconds between reconnect cycles (default: 90)
  --jitter     Random jitter added to interval in seconds (default: 20)
  --count      Number of cycles before stopping; 0 = run forever (default: 0)
  --no-log     Suppress timestamp log output
  --log-file   Path to write log entries (default: stdout only)
  --dry-run    Simulate without actually disconnecting
"""
from __future__ import annotations

import argparse        # stdlib — argument parsing
import os               # stdlib — environment and path helpers
import platform         # stdlib — OS detection (Linux vs macOS dispatch)
import random           # stdlib — jitter randomisation
import subprocess       # stdlib — invokes iw (Johannes Berg), wpa_cli (Jouni Malinen @jmalinen — https://w1.fi/wpa_supplicant/), nmcli (NetworkManager team — https://networkmanager.dev), airport / networksetup (Apple Inc.)
import sys              # stdlib — exit codes and stderr
import time             # stdlib — sleep between cycles
from datetime import datetime   # stdlib — timestamp formatting
from pathlib import Path        # stdlib — log file path handling

VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------
_SYSTEM = platform.system()


def _log(msg: str, log_file: Path | None = None, silent: bool = False) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    if not silent:
        print(line, flush=True)
    if log_file:
        try:
            with open(log_file, "a") as f:
                f.write(line + "\n")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Interface helpers
# ---------------------------------------------------------------------------
def _detect_interface() -> str | None:
    """Return the first active wireless interface found."""
    if _SYSTEM == "Linux":
        try:
            out = subprocess.check_output(["iw", "dev"], text=True, timeout=5)
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("Interface"):
                    return line.split()[-1]
        except Exception:
            pass
        # Fallback: scan /proc/net/wireless
        try:
            with open("/proc/net/wireless") as f:
                for line in f:
                    parts = line.strip().split()
                    if parts and parts[0].endswith(":"):
                        return parts[0].rstrip(":")
        except Exception:
            pass
    elif _SYSTEM == "Darwin":
        try:
            out = subprocess.check_output(
                ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-I"],
                text=True, timeout=5, stderr=subprocess.DEVNULL,
            )
            for line in out.splitlines():
                if "SSID" in line:
                    return "en0"
        except Exception:
            pass
        return "en0"
    return None


def _get_current_ssid(interface: str) -> str | None:
    """Return the SSID the interface is currently associated with, or None."""
    if _SYSTEM == "Linux":
        try:
            out = subprocess.check_output(
                ["iwgetid", interface, "-r"], text=True, timeout=5, stderr=subprocess.DEVNULL
            )
            return out.strip() or None
        except Exception:
            pass
        try:
            out = subprocess.check_output(
                ["iw", interface, "link"], text=True, timeout=5, stderr=subprocess.DEVNULL
            )
            for line in out.splitlines():
                if "SSID:" in line:
                    return line.split("SSID:")[-1].strip()
        except Exception:
            pass
    elif _SYSTEM == "Darwin":
        try:
            out = subprocess.check_output(
                ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-I"],
                text=True, timeout=5, stderr=subprocess.DEVNULL,
            )
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("SSID:"):
                    return line.split(":", 1)[1].strip()
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# Disconnect / reconnect
# ---------------------------------------------------------------------------
def _disconnect(interface: str, dry_run: bool = False) -> bool:
    """Disconnect from the current network."""
    if dry_run:
        return True
    if _SYSTEM == "Linux":
        cmds = [
            ["sudo", "iw", interface, "disconnect"],
            # wpa_supplicant DBUS or CLI
            ["sudo", "wpa_cli", "-i", interface, "disconnect"],
        ]
        for cmd in cmds:
            try:
                result = subprocess.run(cmd, capture_output=True, timeout=10)
                if result.returncode == 0:
                    return True
            except Exception:
                continue
        # NetworkManager fallback
        try:
            subprocess.run(
                ["sudo", "nmcli", "device", "disconnect", interface],
                capture_output=True, timeout=10,
            )
            return True
        except Exception:
            return False

    elif _SYSTEM == "Darwin":
        try:
            subprocess.run(
                ["sudo", "airport", interface, "-z"],
                capture_output=True, timeout=10,
            )
            return True
        except Exception:
            try:
                subprocess.run(
                    ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-z"],
                    capture_output=True, timeout=10,
                )
                return True
            except Exception:
                return False
    return False


def _reconnect(interface: str, ssid: str, dry_run: bool = False) -> bool:
    """Reconnect to the target SSID."""
    if dry_run:
        return True
    if _SYSTEM == "Linux":
        # NetworkManager
        try:
            result = subprocess.run(
                ["sudo", "nmcli", "device", "wifi", "connect", ssid, "ifname", interface],
                capture_output=True, timeout=30,
            )
            if result.returncode == 0:
                return True
        except Exception:
            pass
        # wpa_supplicant fallback
        try:
            subprocess.run(
                ["sudo", "wpa_cli", "-i", interface, "reconnect"],
                capture_output=True, timeout=30,
            )
            return True
        except Exception:
            pass
        # iw association (open networks only)
        try:
            subprocess.run(
                ["sudo", "iw", interface, "connect", ssid],
                capture_output=True, timeout=30,
            )
            return True
        except Exception:
            return False

    elif _SYSTEM == "Darwin":
        # networksetup
        try:
            # Try joining the saved network profile
            result = subprocess.run(
                ["networksetup", "-setairportnetwork", interface, ssid],
                capture_output=True, timeout=30,
            )
            return result.returncode == 0
        except Exception:
            return False

    return False


def _wait_for_association(interface: str, ssid: str, timeout: int = 30) -> bool:
    """Poll until the interface is associated with the expected SSID."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        current = _get_current_ssid(interface)
        if current and current == ssid:
            return True
        time.sleep(2)
    return False


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def drift(
    ssid: str,
    interface: str,
    interval: int = 90,
    jitter: int = 20,
    count: int = 0,
    dry_run: bool = False,
    log_file: Path | None = None,
    silent: bool = False,
) -> None:
    def log(msg: str) -> None:
        _log(msg, log_file=log_file, silent=silent)

    log("=" * 54)
    log(f" Drift v{VERSION} — Wireless Reconnect Client")
    log(f" SSID      : {ssid}")
    log(f" Interface : {interface}")
    log(f" Interval  : {interval}s ± {jitter}s")
    log(f" Cycles    : {'∞' if count == 0 else count}")
    log(f" Dry-run   : {'yes' if dry_run else 'no'}")
    log("=" * 54)

    cycle = 0
    while count == 0 or cycle < count:
        cycle += 1

        # Verify we're connected to the right network before acting
        current = _get_current_ssid(interface)
        if not dry_run and current != ssid:
            log(f"[!] Currently associated with '{current or '(none)'}', not '{ssid}' — skipping cycle {cycle}")
        else:
            log(f"[{cycle}] Disconnecting from '{ssid}'…")
            ok = _disconnect(interface, dry_run=dry_run)
            if ok:
                log(f"[{cycle}] Disconnected. Waiting 3s…")
            else:
                log(f"[{cycle}] Disconnect command returned error — continuing.")

            time.sleep(3)

            log(f"[{cycle}] Reconnecting to '{ssid}'…")
            ok = _reconnect(interface, ssid, dry_run=dry_run)
            if ok:
                if not dry_run:
                    associated = _wait_for_association(interface, ssid, timeout=20)
                    if associated:
                        log(f"[{cycle}] Reconnected to '{ssid}' ✓")
                    else:
                        log(f"[{cycle}] Reconnect issued but association not confirmed within 20s")
                else:
                    log(f"[{cycle}] [dry-run] Reconnect simulated ✓")
            else:
                log(f"[{cycle}] Reconnect command returned error")

        # Sleep until next cycle
        sleep_time = interval + random.randint(-jitter // 2, jitter)
        sleep_time = max(sleep_time, 10)  # minimum 10 seconds
        next_cycle_in = sleep_time
        log(f"[{cycle}] Next cycle in {next_cycle_in}s.")
        try:
            time.sleep(next_cycle_in)
        except KeyboardInterrupt:
            log("Interrupted by user.")
            break

    log(f"Drift complete — {cycle} cycle(s) run.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="drift",
        description="Drift — periodic wireless disconnect/reconnect for misconfiguration testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 drift.py --ssid "CorpWifi" --interval 60 --jitter 15
  python3 drift.py --ssid "Target_AP" --interface wlan1 --count 10
  python3 drift.py --ssid "TestNet" --dry-run --interval 10 --count 3
""",
    )
    parser.add_argument("--ssid",      "-s", required=True,
                        help="Target network SSID to disconnect from and reconnect to")
    parser.add_argument("--interface", "-i", default=None,
                        help="Wireless interface name (auto-detected if omitted)")
    parser.add_argument("--interval",  "-t", type=int, default=90,
                        help="Base interval between cycles in seconds (default: 90)")
    parser.add_argument("--jitter",    "-j", type=int, default=20,
                        help="Random jitter range added to interval in seconds (default: 20)")
    parser.add_argument("--count",     "-n", type=int, default=0,
                        help="Number of disconnect/reconnect cycles; 0 = run forever (default: 0)")
    parser.add_argument("--log-file",  "-l", default=None,
                        help="Write log entries to this file in addition to stdout")
    parser.add_argument("--no-log",    action="store_true",
                        help="Suppress stdout log output (useful with --log-file)")
    parser.add_argument("--dry-run",   action="store_true",
                        help="Simulate cycles without actually disconnecting")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    interface = args.interface
    if not interface:
        interface = _detect_interface()
        if not interface:
            print("[!] Could not auto-detect a wireless interface. Use --interface.", file=sys.stderr)
            sys.exit(1)
        print(f"[*] Auto-detected interface: {interface}", flush=True)

    log_file = Path(args.log_file) if args.log_file else None

    try:
        drift(
            ssid=args.ssid,
            interface=interface,
            interval=args.interval,
            jitter=args.jitter,
            count=args.count,
            dry_run=args.dry_run,
            log_file=log_file,
            silent=args.no_log,
        )
    except KeyboardInterrupt:
        print("\n[*] Drift stopped.", flush=True)
        sys.exit(0)


if __name__ == "__main__":
    main()
