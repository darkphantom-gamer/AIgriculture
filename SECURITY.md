# Security Policy

AIgriculture is a self-hosted appliance that runs on a Raspberry Pi inside the
operator's own farm network. It controls cameras, relays, irrigation, and sends
alerts. The security posture below assumes that deployment model. Anyone
exposing the dashboard directly to the public internet should read the
"Hardening for internet-facing deployments" section before doing so.

## Supported versions

| Version | Status      | Security fixes |
|---------|-------------|----------------|
| 1.0.1   | Current     | Yes            |
| 1.0.0   | Superseded  | Upgrade to 1.0.1 |
| < 1.0.0 | Pre-release | No             |

Only the latest tagged release on the `main` branch receives security fixes.
When 1.1.x ships, 1.0.x will be supported for 30 days after the cut.

### What's new in 1.0.1 (security patch)

Internal black-box pentest fixes — all changes are in `main.py` and
`main-hailo.py` only; the dashboard, login page, email templates, theme,
and all design assets are byte-identical to 1.0.0:

- `/docs`, `/redoc`, `/openapi.json` are **disabled by default**. Opt in
  with `AIGRI_PUBLIC_DOCS=1` only on a trusted dev box.
- **Content-Security-Policy** header now shipped on every response
  (`default-src 'self'`, no framing, no object/embed, locked-down sources).
- **8 MB request-body cap** enforced at the middleware layer (HTTP 413).
- Email validator tightened — rejects HTML / control characters.
- `Server: uvicorn` banner removed.

## Reporting a vulnerability

**Do not open a public GitHub issue for security problems.**

Use one of these private channels instead:

1. **GitHub Security Advisory (preferred)** —
   <https://github.com/darkphantom-gamer/AIgriculture/security/advisories/new>
   This creates a private thread visible only to you and the maintainer.
2. **GitHub direct message** to
   [@darkphantom-gamer](https://github.com/darkphantom-gamer).

When reporting, please include:

- The affected file / endpoint / command
- The version (`git rev-parse --short HEAD` or release tag)
- A minimal reproduction (curl command, request body, or short script)
- The impact you observed (data read, write, RCE, DoS, etc.)
- Whether you are willing to be credited in the fix commit

### What to expect

| Stage                         | Target                            |
|-------------------------------|-----------------------------------|
| Acknowledge receipt           | within 72 hours                   |
| Triage + severity assignment  | within 7 days                     |
| Fix for high / critical       | within 30 days of confirmation    |
| Fix for medium / low          | best effort, batched with releases|
| Public disclosure             | after a fix ships, with credit    |

This is a community project maintained by one person on evenings and weekends.
Timelines are best effort, not contractual.

## Scope

### In scope

- `main.py`, `main-hailo.py`, `flora_*.py`, `farm_monitor_*.py`,
  `meshtastic_flora_bridge.py`
- The HTML/JS shipped under `design/`
- Login, session, and authorization logic
- All HTTP and WebSocket endpoints under `/auth/*`, `/api/*`, `/stream*`
- Default configuration in `.env.example`, `config.example.yaml`,
  `wiring.example.yaml`
- Build / install scripts referenced by the README

### Out of scope

- Upstream vulnerabilities in Python dependencies (please report to the
  upstream project; we will pin or upgrade once a fix is available)
- Vulnerabilities in the Pi OS kernel, libcamera, MariaDB, Hailo runtime, or
  Meshtastic firmware
- Issues that require physical access to the Pi or its SD card
- Issues caused by running with `--reload`, `--debug`, or any flag the docs
  warn against
- Issues caused by setting an empty `JWT_SECRET` *and* an empty `ADMIN_PASS`
  *and* ignoring the random password printed on first boot
- Self-XSS in fields that only the logged-in admin can edit

## Threat model

The intended deployment is:

- A single Pi on a private LAN (often behind NAT, no inbound port forward)
- One or two trusted operators with admin credentials
- Sensors, relays, and cameras owned by the operator
- Optional outbound calls to LLM providers (Groq / Cerebras / Mistral / Gemini)
- Optional outbound SMTP for alert emails
- Optional Meshtastic LoRa radio for offline mesh chat

The attackers we design against:

- An unauthenticated user on the same LAN trying to reach the dashboard
- A guest device on the network running automated credential scans
- A malicious or compromised LLM provider returning crafted responses to FLORA
- A neighbour with a Meshtastic radio injecting messages on the mesh

We **do not** design against:

- A nation-state with physical access to the Pi
- Side-channel attacks on the Pi's CPU or memory
- Compromise of the operator's own laptop or phone

## What is hardened today (v1.0.1)

The shipped defaults in this release implement:

- **Secrets isolation** — real secrets live in `.env` / `.jwt_secret`; only
  `.env.example` and `config.example.yaml` are committed. `.gitignore` blocks
  `.env`, `*.env`, `.jwt_secret`, `*.key`, `*.pem`, `config.yaml`, and
  `*credentials*` / `*secret*` patterns.
- **Password storage** — bcrypt via `passlib.CryptContext(schemes=["bcrypt"])`.
  Plain passwords are never logged or written to disk.
- **Session tokens** — JWT signed with HS256. The signing key is loaded from
  `JWT_SECRET` env var or auto-generated to `.jwt_secret` (chmod `0o600`,
  owner-only). Tokens carry a `jti` checked against the `sessions` table on
  every request — `/auth/logout` revokes the row, so a stolen-but-revoked
  token returns 401 even with a valid signature.
- **Cookie flags** — `pmc_token` is set with `HttpOnly`, `SameSite=Strict`,
  `Path=/`, and `Secure` whenever the request arrived over HTTPS.
- **Login throttle (two layers)** — per-IP throttle on `/auth/login`
  returning HTTP 429 after 5 attempts (in-memory) **plus** a per-user DB
  lock (`users.locked_until`) that persists across restarts. `X-Forwarded-For`
  is **not** trusted for the IP key.
- **SQL** — all queries use parameterized statements (`%s` placeholders with
  tuple arguments). No string concatenation or f-strings build SQL.
- **CORS** — no `CORSMiddleware` is registered, so by default the browser
  rejects cross-origin requests to the API.
- **CSRF** — mitigated by `SameSite=Strict` cookies plus JSON-only POST
  endpoints. There is no token-based CSRF defence; see "Known limitations".
- **Response hardening headers** — every response carries:
  - `Content-Security-Policy` (default-src self, no framing, no object/embed,
    inline scripts/styles allowed for the dashboard only, connect-src self,
    `fonts.googleapis.com` / `fonts.gstatic.com` allow-listed only for the
    Plus Jakarta Sans webfont used by the original theme)
  - `X-Frame-Options: DENY` and `frame-ancestors 'none'`
  - `X-Content-Type-Options: nosniff`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Cross-Origin-Opener-Policy: same-origin`
  - `Permissions-Policy: camera=(self), microphone=(), geolocation=()`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains` —
    automatically emitted when the request arrived over HTTPS.
- **API spec gating** — `/docs`, `/redoc`, `/openapi.json` are **off by
  default**. Set `AIGRI_PUBLIC_DOCS=1` on a trusted dev box to enable them.
  This prevents Swagger UI from leaking the full API surface to anyone who
  finds the dashboard.
- **Request-body cap** — middleware rejects any request with
  `Content-Length > 8 MB` with HTTP 413 before any handler runs. Stops trivial
  body-amplification DoS on the Pi.
- **Server banner suppressed** — uvicorn runs with `server_header=False` so
  fingerprinting tools see no `Server:` header.
- **No-store cache** — auth-bearing responses are wrapped in `_no_store(...)`
  so credentials and session state are not cached by proxies.
- **Static assets** — `/img/<sha256>.<ext>` URLs are content-hashed so that
  cached assets cannot be silently swapped. Filename path traversal
  (`../../etc/passwd`, encoded variants) returns 404, not a file.
- **Email validator** — `^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$`,
  rejects HTML angle brackets and control characters.
- **FLORA outbound calls** — API keys are read from env vars, never written
  to the chat history or logs. The chat history (`.flora_chat_history.json`)
  is git-ignored. FLORA has a tool-based action model, so prompt injection
  cannot trigger arbitrary file reads or shell commands.

## Known limitations

These are deliberate trade-offs for the LAN-appliance model. They are
acceptable in scope; they are **not** acceptable when the dashboard is exposed
to the public internet without the mitigations in the next section.

- **No HTTPS by default** — the server binds plain HTTP on port 8000. TLS is
  the operator's responsibility (reverse proxy, Tailscale, Cloudflare Tunnel,
  etc.).
- **No CSRF token** — protection relies on `SameSite=Strict` + JSON-only
  POSTs. A future release will add a double-submit token for
  internet-exposed deployments.
- **CSP allows `'unsafe-inline'` for scripts and styles** — the dashboard
  ships inline `<script>` and `<style>` blocks for a no-build single-file
  install. The textContent-only rendering on user data still blocks XSS in
  practice; tightening this to nonce-based CSP would require splitting
  `design/dashboard.html` and is reserved for a major release.
- **No 2FA** — single password, single role. A future release will add TOTP.
- **No audit log** — login attempts hit the rate limiter, but there is no
  durable audit trail of who changed what.
- **Mesh inbound** — `MESH_ALLOWED_NODES` is the only filter for inbound
  Meshtastic messages. If left blank, *any* node on the mesh can talk to
  FLORA. Set this on any deployment that shares a mesh with untrusted nodes.
- **LLM prompt injection** — FLORA forwards model output back to the operator
  as plain text. A malicious LLM response cannot execute code on the Pi, but
  it can produce misleading advice. Treat FLORA output as advice, not a
  command channel.

## Hardening for internet-facing deployments

If you must expose AIgriculture to the public internet, at minimum:

1. Put it behind a reverse proxy that terminates TLS
   (Caddy / nginx / Cloudflare Tunnel / Tailscale Funnel).
2. Set `JWT_SECRET` and `ADMIN_PASS` to strong, unique values in `.env`.
3. Restrict `/auth/login` further at the proxy layer (fail2ban, mod_security,
   or Cloudflare rate-limit rules).
4. Add response headers at the proxy:
   - `Strict-Transport-Security: max-age=31536000; includeSubDomains`
   - `X-Frame-Options: DENY`
   - `X-Content-Type-Options: nosniff`
   - `Referrer-Policy: same-origin`
   - `Content-Security-Policy: default-src 'self'; img-src 'self' data:;
     style-src 'self' 'unsafe-inline'; script-src 'self'`
5. Set `MESH_ALLOWED_NODES` to your own node IDs only.
6. Disable SMTP credentials in `.env` if you do not need email alerts; keep
   the attack surface small.
7. Rotate `.jwt_secret` and `ADMIN_PASS` after every operator change.
8. Leave `AIGRI_PUBLIC_DOCS` **unset** in production — only the operator
   needs the API surface map.

## Operator checklist before going live

- [ ] `.env` exists and is not world-readable (`chmod 600 .env`)
- [ ] `.jwt_secret` is owner-only (`stat -c '%a' .jwt_secret` returns `600`)
- [ ] `ADMIN_PASS` is set to a value you have not used elsewhere
- [ ] `DB_PASS` is not the example value
- [ ] `MESH_ALLOWED_NODES` is set if `MESH_ENABLED=true`
- [ ] Reverse proxy with TLS is in front of the Pi if reachable from outside
  the LAN
- [ ] Pi OS is up to date (`sudo apt update && sudo apt full-upgrade`)
- [ ] Python dependencies are up to date
  (`pip list --outdated`)
- [ ] `AIGRI_PUBLIC_DOCS` is **not** set in `.env`
- [ ] `curl -I http://<pi>:8000/login | grep -i content-security` shows the
      CSP header — confirms you are on the 1.0.1+ build

## Safe-harbour for security researchers

If you report a vulnerability through one of the private channels above,
follow these guidelines, and give the maintainer a reasonable window to fix
it before public disclosure, then:

- We will not pursue any legal action for your research
- We will credit you in the fix commit and the release notes, unless you
  prefer to remain anonymous
- We will keep your report confidential until a fix is shipped

Guidelines:

- Test only on hardware you own
- Do not access, modify, or exfiltrate data that does not belong to you
- Do not perform DoS / load testing against shared infrastructure
- Do not socially engineer the maintainer or other contributors

## Credits

Maintainer: The Great Himkamal
([@darkphantom-gamer](https://github.com/darkphantom-gamer)).

Thanks to the security researchers, friends, and farmers who have helped
shape this policy.
