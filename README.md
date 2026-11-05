<details>
<summary><strong>FULL DISCLOSURE</strong> — AI Development & Legal Notice</summary>

---

### AI Development Disclosure

This tool is part of the **pr0t31n toolkit**, a collection of security testing and penetration testing automation tools. The toolkit was created through AI-assisted development, guided by the professional experience and domain expertise of a cybersecurity consultant and penetration tester. Ya, I named it after myself - but to be fair, AI is horrible at naming things.

**The pr0t31n toolkit exists to serve two purposes:**

1. **Automate repetitive penetration testing workflow steps.** Security assessments involve significant amounts of repetitive, procedural work — running sequential tool chains, parsing outputs, correlating findings across tools, and managing engagement data. Automating these steps frees testers to focus on the work that requires human judgment: manual testing, creative attack paths, analysis, and reporting.

2. **Demonstrate the benefits and failures of AI-assisted development.** This toolkit is a real-world case study in building production security tooling with AI assistance. It demonstrates both what AI-assisted development can accomplish and where it falls short. The quality of AI-generated code varies significantly — between context refreshes, the output can range from senior/principal-level software engineering to the work of a still-in-school intern. This inconsistency is itself part of the demonstration.

In the interest of transparency, every tool in the pr0t31n toolkit carries this disclosure. The creator believes that AI-assisted development should be acknowledged openly, not concealed. Users, reviewers, and anyone examining this code should know how it was built so they can evaluate it accordingly.

---

### Legal & Authorization Notice

> **⚠ WARNING: AUTHORIZED USE ONLY**

This tool is designed and intended **exclusively** for use in **authorized security testing engagements**. "Authorized" means **all** of the following conditions are met:

- **Explicit Written Permission.** You possess explicit, documented, written authorization from the owner or authorized representative of the target system(s), network(s), or application(s) to conduct security testing. Verbal agreements are not sufficient.
- **Defined Scope.** The authorization clearly defines the scope of testing, including which systems, networks, IP ranges, applications, and/or endpoints are included. You must not exceed the boundaries of this defined scope under any circumstances.
- **Defined Timeframe.** The authorization specifies the dates and times during which testing is permitted. Testing outside the authorized window is unauthorized testing.
- **Rules of Engagement.** You are operating under a set of rules of engagement (RoE) or equivalent governing document that establishes acceptable testing methods, escalation procedures, emergency contacts, and any restrictions or exclusions.
- **Legal Compliance.** Your testing complies with all applicable local, state, national, and international laws and regulations, including but not limited to the Computer Fraud and Abuse Act (CFAA), the General Data Protection Regulation (GDPR), and equivalent legislation in your jurisdiction.

**Prohibited uses** include but are not limited to: unauthorized access to or testing of any system; testing against systems without explicit written authorization; any activity that violates applicable laws; use for malicious purposes including data theft, extortion, sabotage, or disruption of services; distribution intended to facilitate unauthorized access; and use without a clear legal basis.

**THIS TOOL IS PROVIDED "AS IS," WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NONINFRINGEMENT.**

The creator(s) and contributor(s) accept no responsibility or liability for any damage, loss, legal consequence, or other harm resulting from the use or misuse of this tool — including damage to systems or data, legal penalties or prosecution, loss of data or revenue, and any direct, indirect, incidental, special, consequential, or punitive damages.

**By using this tool, you acknowledge that you are solely responsible for ensuring that your use is authorized, lawful, and within the defined scope of your engagement. You assume all risk associated with the use of this tool.**

Security testing is a professional discipline with significant ethical and legal obligations. Users operating in a professional capacity are expected to adhere to the standards and codes of conduct established by recognized industry bodies, including PTES, OWASP, NIST, and any certifying body under which they hold credentials.

---

</details>

# Drift

**Periodic wireless disconnect/reconnect client** for generating controlled deauthentication and re-association traffic during wireless security assessments.

Drift runs on a device already connected to the target network and repeatedly disconnects and reconnects at a configurable interval. This generates the 4-way handshake retransmissions, PMKID frames, and EAP exchanges needed to test for PMKID capture, KRACK retransmission windows, WPA-Enterprise credential replay, and related wireless misconfiguration vulnerabilities — without requiring a separate attacker-controlled station.

---


> **[View full documentation on the Codex Wiki](https://wiki.pr0t31n.com/tools/drift)** — detailed features, CLI reference, findings catalogue, and integration guides.

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
