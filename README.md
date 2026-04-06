# Drift

**Periodic wireless disconnect/reconnect client** for generating controlled deauthentication and re-association traffic during wireless security assessments.

Drift runs on a device already connected to the target network and repeatedly disconnects and reconnects at a configurable interval. This generates the 4-way handshake retransmissions, PMKID frames, and EAP exchanges needed to test for PMKID capture, KRACK retransmission windows, WPA-Enterprise credential replay, and related wireless misconfiguration vulnerabilities — without requiring a separate attacker-controlled station.

---

## Features

- **Jittered timing** — randomizes sleep between cycles to avoid predictable traffic patterns
- **Association verification** — polls the interface after each reconnect and confirms the SSID matches before proceeding
- **Graceful cycle safety** — checks current SSID before every disconnect; skips the cycle if the interface has drifted to a different network
- **Platform-aware** — cascading fallback chains for disconnect/reconnect on both Linux and macOS
- **Dry-run mode** — simulates the full cycle loop without issuing any wireless commands
- **File logging** — optionally writes timestamped log entries to a file alongside stdout
- **No dependencies** — standard library only; no pip installs required

---

## Requirements

- Python 3.7+
- No external Python packages

**Linux** — one or more of the following must be on `PATH`:

| Tool | Role |
|------|------|
| `iw` | Interface detection, disconnect, link status |
| `iwgetid` | Current SSID lookup |
| `wpa_cli` | wpa_supplicant disconnect / reconnect |
| `nmcli` | NetworkManager disconnect / reconnect (preferred) |
| `sudo` | Privilege escalation for wireless commands |

**macOS** — uses system frameworks; no additional installs needed:

| Tool | Role |
|------|------|
| `airport` (Apple80211 framework) | Interface detection, SSID lookup, disassociate |
| `networksetup` | Reconnect to saved network profile |

---

## Usage

```bash
# Run forever against a WPA2 corporate network (default interval: 90s ± 20s)
python3 drift.py --ssid "CorpWifi"

# Specify interface, faster cycle, bounded run
python3 drift.py --ssid "Target_AP" --interface wlan1 --interval 30 --jitter 10 --count 20

# Log to file (suppress stdout)
python3 drift.py --ssid "CorpWifi" --log-file drift.log --no-log

# Dry-run: verify timing and logic without issuing wireless commands
python3 drift.py --ssid "TestNet" --dry-run --interval 10 --count 5
```

---

## Options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--ssid` | `-s` | *(required)* | Target network SSID |
| `--interface` | `-i` | auto-detected | Wireless interface name |
| `--interval` | `-t` | `90` | Base seconds between cycles |
| `--jitter` | `-j` | `20` | Random seconds added to interval each cycle |
| `--count` | `-n` | `0` | Cycles to run; `0` runs forever |
| `--log-file` | `-l` | stdout only | Append timestamped log entries to this file |
| `--no-log` | | off | Suppress stdout output |
| `--dry-run` | | off | Simulate without disconnecting |

Sleep per cycle is calculated as `interval + randint(-jitter/2, jitter)`, with a minimum floor of 10 seconds.

---

## Platform Behaviour

### Linux

**Interface auto-detection:** `iw dev` → `/proc/net/wireless`

**Disconnect** (tried in order, stops at first success):
1. `sudo iw <iface> disconnect`
2. `sudo wpa_cli -i <iface> disconnect`
3. `sudo nmcli device disconnect <iface>`

**Reconnect** (tried in order):
1. `sudo nmcli device wifi connect <ssid> ifname <iface>`
2. `sudo wpa_cli -i <iface> reconnect`
3. `sudo iw <iface> connect <ssid>` *(open networks only)*

**SSID detection:** `iwgetid <iface> -r` → `iw <iface> link`

### macOS

**Interface auto-detection:** `airport -I` → returns `en0`

**Disconnect:** `airport -z` (Apple80211 disassociate)

**Reconnect:** `networksetup -setairportnetwork <iface> <ssid>`

**SSID detection:** `airport -I` (parses `SSID:` field)

---

## Association Verification

After each reconnect command, Drift polls `_get_current_ssid()` every 2 seconds for up to 30 seconds. If the interface associates with the expected SSID within that window the cycle is logged as successful. If not, a warning is logged and the next sleep begins — the loop does not abort.

---

## Use Cases

| Scenario | Why Drift Helps |
|----------|-----------------|
| **PMKID capture** | Each reconnect broadcasts a new PMKID in the EAPOL frame; attacker running `hcxdumptool` can capture it passively |
| **KRACK / retransmission testing** | Re-association triggers message 3 retransmissions; Drift sustains a steady supply of handshake frames |
| **WPA-Enterprise credential replay** | EAP identity responses replayed during re-authentication expose server-side validation weaknesses |
| **Rogue AP detection** | Confirms whether monitoring tools alert on repeated deauth/assoc events from a legitimate client |
| **Deauth resilience** | Validates that infrastructure correctly handles frequent re-associations without service degradation |

---

## Notes

- Drift must be run on a device that is **already authenticated** to the target network. It does not crack, forge, or inject frames — it uses the OS's own wireless stack to disassociate and re-associate cleanly.
- Commands requiring `sudo` will prompt for a password unless passwordless sudo is configured for `iw`, `nmcli`, or `wpa_cli`.
- On macOS, `airport -z` requires the Airport utility from the Apple80211 private framework. It is present on all macOS versions through at least Ventura.
- Windows is not supported — no equivalent headless wireless association API is used.

---

## Contributors

Drift is pure Python standard library. All wireless operations are delegated to OS-level tools. Credit to their authors:

| Tool | Author / Maintainer | Link |
|------|-------------------|------|
| **iw** | Johannes Berg | https://wireless.wiki.kernel.org/en/users/documentation/iw |
| **iwgetid** (wireless-tools) | Jean Tourrilhes | https://hewlettpackard.github.io/wireless-tools/Tools.html |
| **wpa_cli / wpa_supplicant** | Jouni Malinen @jmalinen | https://w1.fi/wpa_supplicant/ |
| **nmcli / NetworkManager** | NetworkManager contributors (Red Hat / GNOME) | https://networkmanager.dev |
| **airport** (Apple80211) | Apple Inc. | https://developer.apple.com/documentation/corewlan |
| **networksetup** | Apple Inc. | https://ss64.com/mac/networksetup.html |
