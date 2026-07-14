# MuScriptor Studio

**AI-assisted Audio + MIDI music workspace**

> **Make sound. See its shape. Edit its notes.**

MuScriptor Studio is a web-based music creation tool that connects text-to-audio generation, timeline-based audio editing, automatic MIDI transcription, and Piano Roll editing in one focused workspace.

The product is built around a simple flow:

```text
Text prompt
    ↓
Stable Audio generation
    ↓
Audio clip on the timeline
    ↓
MuScriptor transcription
    ↓
MIDI clip / Piano Roll editing
    ↓
Audio + MIDI playback and export
```

## Product direction

MuScriptor Studio is designed as a **DAW with AI inside**, not as a generic AI dashboard. The main surface is an arrangement timeline; generation is a tool invoked from the workspace, and MIDI remains editable musical data rather than a final opaque result.

### Design language: Tactile Signal Studio

- Dark, precise, instrument-console-inspired workspace
- Waveforms and MIDI note grids as primary visual language
- Coral for AI generation, amber for audio, and teal for MIDI
- Dense but calm layout with visible grid lines and restrained motion
- No generic AI sparkle, glassmorphism, or dashboard-style feature-card wall
- Human editing and machine generation shown as one continuous workflow

See [the design language document](docs/design-language.md) for the initial visual and interaction system.

## Runtime and deployment principle

MuScriptor Studio is fundamentally a **personal desktop application**, with a matching Colab deployment for development and remote access.

- On a personal desktop, run the web app locally and use a local GPU when one is available.
- Keep a CPU fallback so the project remains usable without a GPU.
- Also provide a Colab T4 deployment that runs the Studio web app and model runtime on the T4 and exposes it through an HTTPS URL.
- Keep the Studio UI, project format, clip model, and job lifecycle independent from the deployment target.

The default user experience should not require an account, cloud deployment, or always-on remote server. Colab is an additional way to host the same web app for development and testing. See [Deployment and Runtime Modes](docs/runtime-modes.md).

## Current status

The model integration has been functionally validated on a real Colab Tesla T4:

- `stabilityai/stable-audio-open-1.0` and `MuScriptor/muscriptor-medium` loaded on the same GPU
- 4-second and 8-second Stable Audio generation completed
- Generated WAV passed to MuScriptor for MIDI extraction
- Audio generation and transcription also ran concurrently in a smoke test
- The tested path used one generation/transcription job at a time and 20 inference steps

The Studio now has a real model-backed browser path on the Colab T4 deployment:

- Studio server health returned `200` through the HTTPS URL
- Browser loaded the arrangement timeline, Audio/MIDI clips, Piano Roll, and Generate panel
- Runtime status displayed `COLAB T4 · HTTPS` and `Tesla T4 · colab-t4`
- A browser-submitted 4-second job reached `ready`
- Stable Audio generation returned a 44.1 kHz WAV in `8.916s`
- MuScriptor returned a MIDI artifact in the same job
- Browser displayed an audio player and WAV/MIDI download links
- Browser console errors: `0`

The current functional boundary is generation, WAV storage, MIDI extraction, polling, playback, and artifact download. Dynamic insertion into the arrangement timeline, non-destructive editing, and full project export remain next.

This repository is the product workspace. The upstream model fork is maintained separately at [`acidsound/muscriptor`](https://github.com/acidsound/muscriptor), currently using the `ui-improvements` branch for the verified model/UI work.

## Planned architecture

The application core is shared across deployment targets. Only the host and local execution backend change.

```text
                         ┌──────────────────────────────┐
                         │ Shared Studio application     │
                         │ Timeline · Audio · MIDI      │
                         │ Piano Roll · Project / Jobs  │
                         └──────────────┬───────────────┘
                                        │
          ┌─────────────────────────────┴─────────────────────────────┐
          │                                                           │
┌─────────┴─────────┐                                     ┌─────────────┴─────────────┐
│ Desktop deployment │                                     │ Colab T4 deployment       │
│ Browser → localhost│                                     │ Browser → HTTPS URL       │
│ Studio server      │                                     │ HTTPS tunnel / ingress    │
│ Local GPU or CPU   │                                     │ Studio server on T4       │
└─────────┬─────────┘                                     │ Stable Audio + MuScriptor │
          │                                               └─────────────┬─────────────┘
          └───────────────────────┬─────────────────────────────────────┘
                                  │
                   WAV / MIDI / Project storage and export
```

Inside either deployment, the runtime selects a local GPU when available and falls back to CPU when necessary. Colab is not a runtime selector inside the local Studio; it is a separate way to launch and expose the same web app. The first implementation should keep GPU work conservative with one Stable Audio generation at a time, serialized variations, and clear job states in the UI.

## Run the Studio locally

The server uses Python's standard library for HTTP and loads the model runtime lazily when the first job is submitted. Install the model dependencies and configure `HF_TOKEN` before requesting real inference.

```bash
python3 server.py --host 127.0.0.1 --port 7860 --deployment desktop
```

Open `http://127.0.0.1:7860` in a browser. The server exposes:

- `GET /api/health`
- `GET /api/runtime`
- `GET /api/project`
- `POST /api/jobs`
- `GET /api/jobs/<job_id>`
- `GET /api/artifacts/<job_id>/audio.wav`
- `GET /api/artifacts/<job_id>/notes.mid`

A job runs through:

```text
queued → loading_models → generating → transcribing → ready
                                             └→ failed
```

The T4 deployment uses a single worker to avoid unsafe VRAM concurrency.

## Run the Studio on Colab T4

Upload the repository files to `/content/muscriptor-studio`, then run the scripts in order:

```bash
colab exec --session studio-t4 --file scripts/colab_start_studio.py --timeout 60
colab exec --session studio-t4 --file scripts/colab_wait_for_studio.py --timeout 150
colab exec --session studio-t4 --file scripts/colab_start_tunnel.py --timeout 180
colab exec --session studio-t4 --file scripts/colab_wait_for_tunnel.py --timeout 120
```

The final script returns an HTTPS URL for the browser. Stop the app and tunnel before stopping the Colab session:

```bash
colab exec --session studio-t4 --file scripts/colab_stop_studio.py --timeout 60
colab stop --session studio-t4
```

The deployment scripts are intentionally separate from the model installation scripts so the web shell can be validated before loading the large model weights.

## Initial roadmap

- [x] Create the Studio shell and dark design-token system
- [x] Add local/Colab web-server launch path
- [x] Validate Studio shell browser access through Colab T4 HTTPS
- [x] Add real Stable Audio → WAV → MuScriptor → MIDI job
- [x] Add browser job polling, audio preview, and WAV/MIDI artifact links
- [ ] Build dynamic arrangement timeline insertion for generated clips
- [ ] Add non-destructive Audio and MIDI editing
- [ ] Reuse and integrate the MuScriptor Piano Roll editor
- [ ] Link Audio and derived MIDI assets in the project model
- [ ] Add WAV / MIDI / project export beyond individual artifacts
- [ ] Add local hardware detection and GPU/CPU runtime selection
- [x] Validate model-backed Colab T4 browser E2E for a 4-second job
- [ ] Stress-test longer clips, higher inference steps, and queue behavior
- [ ] Add secure/persistent remote-access option beyond unauthenticated temporary tunnels

## Repository layout

```text
.
├── README.md
├── server.py
├── model_runtime.py
├── web/
│   └── index.html
├── scripts/
│   ├── colab_start_studio.py
│   ├── colab_wait_for_studio.py
│   ├── colab_start_tunnel.py
│   ├── colab_wait_for_tunnel.py
│   └── colab_stop_studio.py
└── docs/
    ├── design-language.md
    └── runtime-modes.md
```

## Security and generated artifacts

- Never commit Hugging Face tokens, `.env` files, cookies, or access credentials.
- Generated audio, MIDI, model caches, checkpoints, and runtime logs stay outside Git by default.
- Do not put raw transcripts or private project assets in public issues or pull requests.
- A temporary HTTPS tunnel may be publicly reachable and unauthenticated; use it only for controlled testing until an authentication and access-control layer is implemented.
- Use short-lived runtime credentials and stop temporary Colab sessions and tunnels after validation.

## License

License terms for the Studio product have not been selected yet. The project currently depends on the separately licensed MuScriptor and Stable Audio components; review their licenses before distributing a combined application.
