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

## Runtime principle: local-first

MuScriptor Studio is fundamentally a **personal desktop application**.

- Use a local GPU when one is available.
- Keep a CPU fallback so the project remains usable without a GPU.
- Also provide a Colab T4 deployment that runs the Studio web app and model runtime on the T4 and exposes it through an HTTPS URL.
- Keep the Studio UI, project format, clip model, and job contract independent from the deployment target.

The default user experience should not require an account, a cloud deployment, or an always-on remote server. Colab is an additional way to host the same web app for temporary remote access. See [Deployment and Runtime Modes](docs/runtime-modes.md) for the execution and exposure model.

## Current status

The model integration has been functionally validated on a real Colab Tesla T4:

- `stabilityai/stable-audio-open-1.0` and `MuScriptor/muscriptor-medium` loaded on the same GPU
- 4-second and 8-second Stable Audio generation completed
- Generated WAV passed to MuScriptor for MIDI extraction
- Audio generation and transcription also ran concurrently in a smoke test
- The tested path used one generation/transcription job at a time and 20 inference steps

The local GPU and CPU paths are product requirements. Their performance and model-specific compatibility still need to be measured separately rather than inferred from the Colab result. The Colab HTTPS web-app deployment is the next integration milestone; the model smoke test alone does not verify the complete browser-accessible deployment.

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

## Initial roadmap

- [ ] Create the Studio shell and dark design-token system
- [ ] Build the arrangement timeline with Audio and MIDI lanes
- [ ] Add the Generate Audio drawer and job states
- [ ] Insert generated audio into the timeline
- [ ] Connect MuScriptor transcription to generated clips
- [ ] Reuse and integrate the MuScriptor Piano Roll editor
- [ ] Link Audio and derived MIDI assets
- [ ] Add WAV / MIDI / project export
- [ ] Add local hardware detection and GPU/CPU runtime selection
- [ ] Add local desktop web-app launch and browser workflow
- [ ] Add Colab T4 deployment script: build, start, HTTPS tunnel, health check
- [ ] Add secure/persistent remote-access option beyond unauthenticated temporary tunnels
- [ ] Stress-test longer clips, higher inference steps, and queue behavior

## Repository layout

```text
.
├── README.md
├── docs/
│   ├── design-language.md
│   └── runtime-modes.md
└── (Studio application code will be added next)
```

## Security and generated artifacts

- Never commit Hugging Face tokens, `.env` files, cookies, or access credentials.
- Generated audio, MIDI, model caches, checkpoints, and runtime logs stay outside Git by default.
- Do not put raw transcripts or private project assets in public issues or pull requests.
- A temporary HTTPS tunnel may be publicly reachable and unauthenticated; use it only for controlled testing until an authentication and access-control layer is implemented.
- Use short-lived runtime credentials and stop temporary Colab sessions and tunnels after validation.

## Development notes

The repository is intentionally starting with product documentation and design constraints before the full UI implementation. The next milestone is a verified Studio shell with three states:

1. Empty Studio
2. Studio with a generated Audio clip
3. Studio with linked Audio and MIDI clips

## License

License terms for the Studio product have not been selected yet. The project currently depends on the separately licensed MuScriptor and Stable Audio components; review their licenses before distributing a combined application.
