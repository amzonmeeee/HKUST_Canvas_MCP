# HKUST Canvas Workbench v3.1.0

This release adds local transcription of HKUST RVC lecture recordings.

## New

- **RVC recordings as sources.** Canvas pages with RVC titles (for example `COMP1000-L1-2026-09-01-09-00`) show under **RVC recordings**. The app finds them in the Pages list, and in links on pages that you sync, such as module pages. A sync does not transcribe a recording.
- **Optional local transcriber.** Open a recording and select **Install transcriber**. The app downloads the separate [RVC_Transcriber](https://github.com/amzonmeeee/RVC_Transcriber) component at a pinned commit, and checks its git tree hash. The component then downloads approximately 4–5 GB (Python, FFmpeg and a speech model) into the app data folder. **Remove transcriber** deletes it again; transcripts stay.
- **Transcripts you can cite.** Select **Transcribe**. The component reads only the audio of the recording and makes a timestamped transcript on your Mac. The transcript becomes a ready source and joins your selection. Chat and Studio cite it by time, for example `Time 00:12:34`. You can stop a transcription and continue it later.
- **Shorter README.** The README follows ASD-STE100. Setup, privacy, providers, MCP, troubleshooting and uninstall details are in [docs/user-guide.md](https://github.com/amzonmeeee/HKUST_Canvas_MCP/blob/v3.1.0/docs/user-guide.md).

## Privacy

Audio is not sent to a server. To get a stream link, the backend reads your Chrome cookie for `rvcmedia.ust.hk`. The cookie and the short-lived stream link stay in the backend. They are not sent to AI providers. The file with the stream link is deleted after each run.

## Downloads

Use the Apple Silicon DMG or zipped app. Move the app to Applications and open it. Developers can install the wheel with its `[web]` extra. The source distribution and `SHA256SUMS` are included.

**Signing:** macOS artifacts are ad-hoc signed. They are not Developer ID signed or notarized. If macOS blocks a trusted download, use **System Settings → Privacy & Security → Open Anyway**. Do not disable Gatekeeper.

## Verification scope

CI runs synthetic Python, frontend, browser and package checks on Ubuntu 24.04 and macOS 15, and builds and smoke-tests the native arm64 app. The transcriber tests use a fake component with the same command-line contract. On a real HKUST course, recording discovery, stream-link resolution and the component's dry run were checked. A full real install and transcription were not run in CI, because they download several GB. Transcription needs an Apple Silicon Mac; the packaged app's path that gets Python for the component through uv was not tested on a fresh machine.

## Upgrade

Updates keep saved work. No database schema change. Zoom cloud recordings are not supported.

MIT licensed. Independent of HKUST, Instructure and AI providers.
