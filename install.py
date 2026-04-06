#!/usr/bin/env python3
"""
install.py — Drift installer
=============================
Drift uses only the Python standard library, so there are no pip packages to
install.  This script verifies that the required OS wireless tools are present
and prints their locations, or explains what to do if they are missing.

Platform handling:
  Linux  — checks iw, iwgetid, wpa_cli, nmcli, sudo
  macOS  — checks airport (Apple80211 framework), networksetup

Usage:
  python3 install.py
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys

VERSION = "1.0.0"

_SYSTEM = platform.system()

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------
_LINUX_TOOLS = [
    {
        "bin":     "iw",
        "pkg_apt": "iw",
        "purpose": "Interface detection, disconnect, and link status",
        "required": True,
    },
    {
        "bin":     "iwgetid",
        "pkg_apt": "wireless-tools",
        "purpose": "Current SSID lookup",
        "required": False,
    },
    {
        "bin":     "wpa_cli",
        "pkg_apt": "wpasupplicant",
        "purpose": "wpa_supplicant disconnect / reconnect fallback",
        "required": False,
    },
    {
        "bin":     "nmcli",
        "pkg_apt": "network-manager",
        "purpose": "NetworkManager disconnect / reconnect (preferred path)",
        "required": False,
    },
    {
        "bin":     "sudo",
        "pkg_apt": "sudo",
        "purpose": "Privilege escalation for wireless commands",
        "required": True,
    },
]

_MACOS_TOOLS = [
    {
        "bin": (
            "/System/Library/PrivateFrameworks/Apple80211.framework"
            "/Versions/Current/Resources/airport"
        ),
        "display": "airport",
        "purpose": "Interface detection, SSID lookup, and disassociate (-z)",
        "required": True,
        "install_hint": "Part of macOS Apple80211 private framework — no install needed",
    },
    {
        "bin":     "networksetup",
        "display": "networksetup",
        "purpose": "Reconnect to a saved wireless network profile",
        "required": True,
        "install_hint": "Built-in macOS system utility — no install needed",
    },
]


def _banner() -> None:
    print("=" * 56)
    print(f"  Drift {VERSION} — Installer / Environment Checker")
    print("=" * 56)
    print()


def _check_python() -> None:
    print("[*] Checking Python version...")
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 7):
        print(f"[!] Python 3.7+ required; found {major}.{minor}. Please upgrade.")
        sys.exit(1)
    print(f"    Python {major}.{minor} — OK")
    print()


def _check_linux_tools() -> None:
    print("[*] Checking Linux wireless tools...")
    missing_required: list[str] = []
    missing_optional: list[str] = []

    for tool in _LINUX_TOOLS:
        path = shutil.which(tool["bin"])
        if path:
            print(f"    [OK]      {tool['bin']:<14}  {path}  — {tool['purpose']}")
        else:
            marker = "[REQUIRED]" if tool["required"] else "[optional]"
            print(f"    {marker}  {tool['bin']:<14}  NOT FOUND — {tool['purpose']}")
            if tool["required"]:
                missing_required.append(tool["bin"])
            else:
                missing_optional.append(tool["bin"])

    print()

    if missing_required or missing_optional:
        all_missing = list(dict.fromkeys(
            [t["pkg_apt"] for t in _LINUX_TOOLS
             if t["bin"] in missing_required + missing_optional]
        ))
        print("[*] To install missing tools on Debian/Ubuntu/Kali:")
        print(f"      sudo apt-get install -y {' '.join(all_missing)}")
        print()

    if missing_required:
        print("[!] One or more REQUIRED tools are missing. Drift may not function correctly.")
    else:
        print("[+] All required tools are present.")
    print()


def _check_macos_tools() -> None:
    print("[*] Checking macOS wireless tools...")

    for tool in _MACOS_TOOLS:
        bin_path = tool["bin"]
        display  = tool.get("display", bin_path)
        # Check absolute path first, then PATH
        if os.path.exists(bin_path) or shutil.which(bin_path):
            found_at = bin_path if os.path.exists(bin_path) else shutil.which(bin_path)
            print(f"    [OK]  {display:<18}  {found_at}  — {tool['purpose']}")
        else:
            print(f"    [!!]  {display:<18}  NOT FOUND — {tool['purpose']}")
            hint = tool.get("install_hint", "")
            if hint:
                print(f"          Hint: {hint}")

    print()
    print("[+] macOS tools checked. Both are built into macOS and should always be present.")
    print()


def _check_pip_packages() -> None:
    print("[*] Checking Python packages...")
    print("    Drift uses only the Python standard library.")
    print("    No pip packages required — nothing to install.")
    print()


def _install_symlinks() -> None:
    """Create /usr/local/bin symlink for all-user access (including root/sudo)."""
    import stat
    from pathlib import Path
    app_dir = Path(__file__).parent.resolve()
    bin_dir = Path("/usr/local/bin")

    LINKS = [
        ("drift.py", "drift"),
    ]

    try:
        bin_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        print("[!] Cannot access /usr/local/bin — run as root to install symlink.")
        return

    for script_name, link_name in LINKS:
        script = app_dir / script_name
        link   = bin_dir / link_name
        if not script.exists():
            print(f"[~] Script not found, skipping: {script}")
            continue
        # Make executable
        current = script.stat().st_mode
        script.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        # Ensure shebang
        try:
            text = script.read_text(encoding="utf-8", errors="ignore")
            if not text.startswith("#!"):
                script.write_text("#!/usr/bin/env python3\n" + text)
        except Exception:
            pass
        # Create/replace symlink
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(script)
        print(f"[+] Symlink: {link}  →  {script}")


def main() -> None:
    _banner()
    _check_python()
    _check_pip_packages()

    if _SYSTEM == "Linux":
        _check_linux_tools()
    elif _SYSTEM == "Darwin":
        _check_macos_tools()
    else:
        print(f"[!] Unsupported platform: {_SYSTEM}. Drift supports Linux and macOS only.")
        sys.exit(1)

    _install_symlinks()

    print("[+] Drift installer / environment check complete.")
    print("    Run:  drift --ssid <SSID> --dry-run")
    print()


if __name__ == "__main__":
    main()
