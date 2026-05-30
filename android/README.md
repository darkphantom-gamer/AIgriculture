# AIgriculture — Android app

A **native** Android client for an AIgriculture Raspberry Pi server. It is not a
web view: every screen is built in Jetpack Compose and talks to the Pi over the
server's existing JSON + WebSocket API, so it behaves like a regular app.

> Status: **vertical slice** — Connect → Login → FLORA chat → Status (live
> sensors + pump control) → Settings. FarmMonitor, Security camera, Analytics
> and Storage screens are landing in the next builds.

## Flow

1. **Connect** — enter the Pi's address (`192.168.1.50:8000`, or an
   `https://` domain). The app verifies it's an AIgriculture server.
2. **Login** — native form → `POST /auth/login`. The session cookie is captured
   and replayed on every request and the WebSocket handshake (no backend change).
3. **FLORA** — chat over `WS /ws/flora` with the Cloud/Offline pill from
   `/api/flora/status`; falls back to `POST /api/flora/chat` if a proxy blocks
   WebSockets.
4. **Status** — live readings via `WS /ws` (1 s push), with per-plant
   Water/Stop (`/api/pump/...`) and the auto-irrigation toggle.

## Design

Theme tokens (colors, radius, dark palette) are taken **directly** from
`design/dashboard.html` so the look matches the web dashboard. Typeface swap to
Plus Jakarta Sans is a tracked polish item.

## Build

CI builds a debug APK on every push (`.github/workflows/android.yml`) and uploads
it as the **AIgriculture-debug-apk** artifact.

Locally (needs the Android SDK + JDK 17):

```bash
cd android
gradle wrapper --gradle-version 8.9   # first time, to create ./gradlew
./gradlew :app:assembleDebug
# APK: app/build/outputs/apk/debug/app-debug.apk
```

Then sideload the APK onto a phone (enable “install unknown apps”).

- **Package:** `com.aigriculture.app`  ·  **Min Android:** 8.0 (API 26)
