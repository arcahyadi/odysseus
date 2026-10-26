# Troubleshooting

A page of 30-second fixes for traps that otherwise turn into 30-minute
searches. Extracted from `docs/setup.md` so it can be linked directly when
someone hits an issue. If a fix here doesn't work, open an issue with the
exact error text and your platform (native Linux, macOS, Windows, WSL2,
Docker; GPU vendor; how you started the app).

## Contents

- [Install / startup](#install--startup)
  - [ChromaDB silently falls back to HTTP-only mode](#chromadb-silently-falls-back-to-http-only-mode)
  - [`AUTH_ENABLED=false` is ignored on Windows](#auth_enabledfalse-is-ignored-on-windows)
  - [macOS: app isn't at `http://localhost:7000`](#macos-app-isnt-at-httplocalhost7000)
  - [Windows: cookbook can't find `bash` / runs a WSL stub](#windows-cookbook-cant-find-bash--runs-a-wsl-stub)
  - [Python locale errors on Windows (`charmap`, `UnicodeDecodeError`)](#python-locale-errors-on-windows-charmap-unicodedecodeerror)
- [Networking / exposure](#networking--exposure)
  - [Copy buttons do nothing over a plain-HTTP LAN / Tailscale URL](#copy-buttons-do-nothing-over-a-plain-http-lan--tailscale-url)
  - [Exposing on a LAN / Tailscale from Windows](#exposing-on-a-lan--tailscale-from-windows)
  - [HTTPS with a locally-trusted cert](#https-with-a-locally-trusted-cert)
- [Integrations](#integrations)
  - [Self-hosted ntfy doesn't reach your phone](#self-hosted-ntfy-doesnt-reach-your-phone)
  - [Dovecot: "Plaintext authentication disallowed on non-encrypted connections"](#dovecot-plaintext-authentication-disallowed-on-non-encrypted-connections)
  - [Radicale calendar / contacts won't sync](#radicale-calendar--contacts-wont-sync)
  - [Outlook / Office 365 login fails](#outlook--office-365-login-fails)
- [Cookbook (model serving)](#cookbook-model-serving)
  - [vLLM / SGLang won't start on native Windows](#vllm--sglang-wont-start-on-native-windows)
  - [WSL2: `nvidia-smi` returns nothing inside the distro](#wsl2-nvidia-smi-returns-nothing-inside-the-distro)
  - [`tmux` missing on non-interactive shells](#tmux-missing-on-non-interactive-shells)
  - [llama-cpp-python: `Illegal instruction` on start](#llama-cpp-python-illegal-instruction-on-start)
  - [SGLang: `sglang-kernel` version mismatch after an upgrade](#sglang-sglang-kernel-version-mismatch-after-an-upgrade)
  - [Cookbook SSH: `Host key verification failed` after the remote rebuilt](#cookbook-ssh-host-key-verification-failed-after-the-remote-rebuilt)
  - [AMD / consumer GPU: vLLM / SGLang refuse to load a model](#amd--consumer-gpu-vllm--sglang-refuse-to-load-a-model)

## Install / startup

### ChromaDB silently falls back to HTTP-only mode

If `chromadb-client` (the lightweight HTTP-only package) is installed
alongside the full `chromadb` package, Odysseus starts but the embedded
ChromaDB silently degrades to HTTP-only and then fails.

Fix — force-reinstall the full package:

```bash
./venv/bin/pip uninstall chromadb-client -y
./venv/bin/pip install --force-reinstall chromadb
```

### `AUTH_ENABLED=false` is ignored on Windows

If you edited `.env` in Notepad it may have saved a UTF-8 **BOM**, so the
first key is `\ufeffAUTH_ENABLED` and never matches. Odysseus now loads
`.env` with `encoding="utf-8-sig"` to tolerate a leading BOM, but the safe
fix is to re-save `.env` as **UTF-8 without BOM** (VS Code:
*Save with Encoding → UTF-8*).

### macOS: app isn't at `http://localhost:7000`

macOS AirPlay Receiver usually holds port `7000`, so the macOS start script
serves on **`7860`** instead. Open `http://localhost:7860`.

To use `7000` — free it (System Settings → General → AirDrop & Handoff →
turn off *AirPlay Receiver*), then set `APP_PORT=7000`.

### Windows: cookbook can't find `bash` / runs a WSL stub

Native Windows has no real `bash`. If you have **Git for Windows** installed
(https://git-scm.com/download/win), `core.platform_compat.find_bash()` locates
its `bash.exe`. If only the WSL stub is on `PATH`, running a shell script
fails with `execvpe(/bin/bash) failed` — install Git for Windows, or invoke
the Cookbook through WSL2 / a Docker container instead of native Windows.

### Python locale errors on Windows (`charmap`, `UnicodeDecodeError`)

Windows' default subprocess / `read_text` locale is `cp1252`. Any file that
contains non-ASCII characters (`→`, `·`, emoji, non-Latin scripts) will crash
a `subprocess.run(text=True)` or `Path.read_text()` call that doesn't pin
encoding. If you see `'charmap' codec can't encode character` or
`'charmap' codec can't decode byte 0x8f` in a log or test, the fix is to add
`encoding="utf-8"` (and usually `errors="replace"` for subprocess output).
The whole test suite is already green on Windows using this pattern; PRs
that reintroduce the failure will show up here first.

## Networking / exposure

### Copy buttons do nothing over a plain-HTTP LAN / Tailscale URL

Browsers only expose the Clipboard API (`navigator.clipboard`) on
**secure origins** — HTTPS or `localhost`. Over
`http://100.x.y.z:7860` (or any plain-HTTP LAN/Tailscale URL) it is
silently blocked. Serve over HTTPS (see next section), or SSH-tunnel to
`localhost:7000` so the browser sees a secure origin.

### Exposing on a LAN / Tailscale from Windows

The Windows launcher binds `127.0.0.1` and does **not** read `APP_BIND`
or `ODYSSEUS_HOST` from `.env`, so editing `.env` alone leaves the native
Windows server on loopback. Pass the launcher's `-BindHost` flag:

```powershell
powershell -ExecutionPolicy Bypass -File .\launch-windows.ps1 -BindHost 0.0.0.0
```

The manual `uvicorn` command takes the same address as `--host 0.0.0.0`.
Bind outside loopback only for a trusted LAN/VPN such as Tailscale —
keep `AUTH_ENABLED=true` and never expose the port to the public internet.

### HTTPS with a locally-trusted cert

1. Set `APP_BIND=0.0.0.0` (or `ODYSSEUS_HOST=0.0.0.0`) in `.env`.
2. Generate a cert covering your LAN IP / Tailscale IP with
   [mkcert](https://github.com/FiloSottile/mkcert):
   ```bash
   mkcert -install
   mkcert -cert-file cert.pem -key-file key.pem 192.168.1.100 tailscale-ip
   ```
3. Run `uvicorn` with the cert:
   ```bash
   python -m uvicorn app:app --host 0.0.0.0 --port 7000 \
       --ssl-certfile=cert.pem --ssl-keyfile=key.pem
   ```
4. Install the `mkcert` root CA on every other device that will access
   Odysseus (for iOS: email `rootCA.pem` to yourself, install the profile,
   then trust it in *Settings → General → About → Certificate Trust
   Settings*).

Also set `SECURE_COOKIES=true` when serving through HTTPS so session
cookies carry the `Secure` flag.

## Integrations

### Self-hosted ntfy doesn't reach your phone

Two things:

1. The bundled ntfy binds loopback by default. Set `NTFY_BIND` to your
   host / Tailscale IP in `.env`, and set `NTFY_BASE_URL` to the same
   server URL, then recreate the ntfy container (see the `NTFY_*` block
   in `.env.example`).
2. In the ntfy **Android** app, subscribe to the topic with
   **Instant delivery** turned on. Non-`ntfy.sh` servers do not get
   instant push over FCM without it — messages arrive only when the app
   is foregrounded.

### Dovecot: "Plaintext authentication disallowed on non-encrypted connections"

Your IMAP / SMTP server is refusing cleartext auth over an unencrypted
link. Prefer enabling TLS on the mail server. On a trusted LAN only, you
can allow cleartext in Dovecot:

```
# /etc/dovecot/conf.d/10-auth.conf
disable_plaintext_auth = no
```

Restart Dovecot, and keep `AUTH_ENABLED=true` on the Odysseus side so a
stranger on the LAN still can't log in.

### Radicale calendar / contacts won't sync

Point Odysseus at the **full collection URL** with its trailing slash —
e.g. `http://host:5232/<user>/<collection-id>/` — not just the server
root. Radicale shows this address for each calendar / address book in
its web UI. Missing the trailing slash yields a successful-looking test
that then syncs nothing.

### Outlook / Office 365 login fails

Odysseus' email path is IMAP/SMTP username-password. Microsoft mail
generally requires OAuth, so ordinary Outlook.com / M365 passwords
fail. See [email-outlook.md](email-outlook.md) for the current
limitation and the planned integration direction.

## Cookbook (model serving)

### vLLM / SGLang won't start on native Windows

Neither upstream ships a native-Windows wheel — treat this as unsupported.
Use **WSL2** with the CUDA drivers on the host, or Docker, for GPU serving
on a Windows box. For a fully local model on native Windows, use
**Ollama** (https://ollama.com/download) and point Odysseus at
`http://localhost:11434/v1` in Settings.

### WSL2: `nvidia-smi` returns nothing inside the distro

WSL exposes the GPU via `/usr/lib/wsl/lib/nvidia-smi`. The first call
sometimes returns nothing because of driver / `ld` cache cold-start.
Odysseus's hardware probe handles this by trying `/usr/lib/wsl/lib` in
addition to `PATH` (see `services/hwfit/hardware.py:88-101`), but if
your distro isn't seeing the GPU at all, ensure you're running inside
WSL2 (not WSL1) with the same NVIDIA driver version as the Windows host,
and that `/usr/lib/wsl/lib/nvidia-smi` exists and prints output when run
by hand.

### `tmux` missing on non-interactive shells

Cookbook serve dispatch runs inside tmux so sessions survive the web
process. On non-interactive shells (SSH one-shot, some minimal distros),
`tmux` may not be on `PATH`, and the runner script prints:

```
WARNING: tmux missing and auto-install failed (need passwordless sudo).
Install manually.
```

Install tmux yourself (`apt install tmux`, `dnf install tmux`,
`pacman -S tmux`) — auto-install is best-effort and won't prompt for a
sudo password on a non-TTY.

### llama-cpp-python: `Illegal instruction` on start

The precompiled `llama-cpp-python` wheel is built for AVX2 / FMA
instruction sets. On older CPUs (pre-Haswell Intel, pre-Excavator AMD)
or on a VM that doesn't expose AVX2, importing the wheel crashes with
`Illegal instruction (core dumped)`.

Fix — build the wheel from source for your CPU:

```bash
CMAKE_ARGS="-DGGML_NATIVE=ON" pip install --force-reinstall --no-cache-dir \
    --config-settings editable_mode=compat -e llama-cpp-python
```

Or install into a VM with AVX2 passthrough. Odysseus's Cookbook diagnosis
panel flags this exact mismatch (`static/js/cookbook-diagnosis.js:711`)
and offers a "Rebuild" action when it detects it.

### SGLang: `sglang-kernel` version mismatch after an upgrade

An `sglang` upgrade frequently leaves the older `sglang-kernel` behind,
producing `ImportError` / `AttributeError` at serve time. Odysseus's
diagnosis panel offers **Repair sglang-kernel**, which runs:

```bash
python -m pip install -U --force-reinstall --no-cache-dir sglang-kernel
```

Copy that into your venv / uv-managed env if the button doesn't fire
(e.g., for a remote SSH target outside the browser).

### Cookbook SSH: `Host key verification failed` after the remote rebuilt

If a remote GPU box was reinstalled / recreated with the same hostname
and IP, OpenSSH reports a host-key mismatch:

```
Host key verification failed.
Offending key for IP ...
```

Odysseus stores per-Cookbook-host keys under its own `known_hosts`.
Use the **"Repair host key"** action in the Cookbook SSH panel — it
wraps `ssh-keygen -R` and `ssh-keyscan` scoped to just that host
(`routes/cookbook_routes.py:783`). If you must do it by hand, refresh
the file Odysseus uses (under `data/ssh/known_hosts`), not your
`~/.ssh/known_hosts`.

### AMD / consumer GPU: vLLM / SGLang refuse to load a model

Consumer RDNA cards (RX 6000 / 7000 series) have limited upstream
support in vLLM / SGLang. Odysseus's hardware fit deliberately treats
them as **GGUF-only** — you'll see llama.cpp options in the
recommended serve list, not vLLM / SGLang. That's not a bug; it's
reflecting what upstream supports reliably. For a consumer AMD card,
download a GGUF quant and serve via llama.cpp / Ollama.

---

If you hit something not on this list, add it — a one-paragraph PR to
this page is exactly as valuable as a code fix.
