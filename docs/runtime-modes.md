# Deployment and Runtime Modes

MuScriptor Studio has two first-class deployment targets:

1. **Desktop deployment** — run the Studio web app and model runtime on a personal computer, using a local GPU when available and CPU otherwise.
2. **Colab T4 deployment** — run the same Studio web app and model runtime inside a Colab T4 session, then access it from a browser through an HTTPS URL.

Colab is not primarily a model API provider selected inside the local Studio. It is an alternate host for the complete web application.

## Product model

```text
                         Shared Studio application
                  Timeline · Audio · MIDI · Piano Roll
                                      │
            ┌─────────────────────────┴─────────────────────────┐
            │                                                   │
   Desktop deployment                                  Colab T4 deployment
   Browser → localhost                                  Browser → HTTPS URL
   Studio server                                         Tunnel / ingress
   Local GPU or CPU                                      Studio server on T4
                                                         T4 GPU model runtime
```

The project format, clip model, UI, job lifecycle, and export behavior should remain the same in both deployments.

## Desktop deployment

Desktop is the default product experience.

```text
Browser or desktop shell
          ↓
Local Studio server
          ↓
Local execution runtime
    ┌───────────────┐
    │ GPU if present │
    │ CPU fallback   │
    └───────────────┘
```

### Local GPU

Use a supported local GPU when available. The runtime should detect the device, report capability, and keep model loading and memory policy local to the user's machine.

The first implementation should prioritize CUDA-capable local GPUs. Other local GPU backends, such as Apple Silicon/MPS, can use the same interface after model-specific validation.

### Local CPU

CPU is a first-class compatibility fallback:

- Audio playback, timeline editing, MIDI editing, and export remain local.
- Stable Audio generation and MuScriptor transcription use CPU-compatible implementations where supported.
- The UI shows an honest “may take longer” state rather than appearing frozen.
- Startup time, inference time, safe duration, and memory limits must be benchmarked before claiming production readiness.

CPU fallback is a product requirement, not a claim that every model configuration has already been performance-validated.

## Colab T4 deployment

The Colab target is a temporary or low-cost remote deployment of the complete Studio application.

```text
1. Allocate a Colab T4 session
2. Install pinned application/model dependencies
3. Start the Studio backend and frontend in the T4 runtime
4. Run the health/readiness checks
5. Start an HTTPS tunnel or ingress to the local Studio port
6. Return the HTTPS URL to the user
7. Use the Studio from any supported browser
8. Stop the tunnel and Colab session when finished
```

The browser should talk to the Studio web app through the HTTPS URL. The browser should not need to know whether Stable Audio and MuScriptor are local processes, Python workers, or model components inside the Colab runtime.

### Colab deployment responsibilities

The deployment script should:

- allocate or reuse a named T4 session
- install reproducible, pinned dependencies
- clone or mount the required model/runtime code
- inject Hugging Face credentials only into the protected runtime environment
- start the Studio server and frontend
- wait for a real health/readiness signal
- create an HTTPS endpoint for the running web app
- return the URL without exposing tokens or private paths
- verify browser-relevant API and WebSocket paths
- stop the tunnel and runtime after cancellation or completion

The current model smoke test validates the combined Stable Audio + MuScriptor path on a T4. It does not yet validate the complete browser-accessible HTTPS deployment; that is a separate integration milestone.

## HTTPS exposure and security

A temporary Quick Tunnel or equivalent HTTPS tunnel is useful for development and controlled demos, but it may be publicly reachable and unauthenticated.

Rules for the initial deployment:

- Treat the temporary URL as public.
- Do not put credentials, raw transcripts, private project files, or internal filesystem paths in the URL, logs, or UI.
- Do not use an unauthenticated public tunnel for sensitive projects.
- Stop the tunnel and the Colab session after testing.
- Add an authentication/access-control layer before treating the deployment as persistent or multi-user.
- Prefer a private overlay-network URL when the goal is personal access rather than public sharing.

The HTTPS URL is an access mechanism, not an authorization mechanism.

## Deployment selection UX

Deployment selection happens before the app is launched, not as a normal Studio runtime dropdown.

```text
Launch target
  Local desktop
  Colab T4 · HTTPS
```

Once the Studio is open, the main UI may show a small non-intrusive status indicator:

```text
Local · GPU
Local · CPU fallback
Colab T4 · HTTPS connected
```

The indicator describes where the current Studio session is running. It should not turn the arrangement workspace into a hardware dashboard.

## Internal execution contract

Inside either deployment, Stable Audio and MuScriptor use the same internal job lifecycle:

```text
queued → generating → extracting-midi → ready
                                  └→ failed / cancelled
```

Example generation request:

```json
{
  "type": "audio-generation",
  "prompt": "warm analog bass loop, 120 BPM, four bars",
  "duration_seconds": 8,
  "project_bpm": 120,
  "seed": null,
  "extract_midi": true
}
```

The API is provisional. The important boundary is that the Studio UI does not need separate product logic for desktop and Colab deployments.

## Data locality

| Data | Desktop deployment | Colab T4 deployment |
|---|---|---|
| Project metadata | Local machine by default | Stored in the temporary runtime unless downloaded/exported |
| Prompt | Local server by default | Sent to the Colab Studio server through HTTPS |
| Generated WAV/MIDI | Local project directory | Created in Colab and downloaded/exported to the user |
| HF token | Protected local runtime only | Protected temporary Colab runtime only |
| Model cache | Local machine cache | Temporary Colab cache |
| Raw transcript / logs | Local and private by default | Must not be exposed through public URLs or logs |

The UI should clearly indicate when the current session is running remotely in Colab.

## Resource policy

GPU memory is not an unlimited concurrency pool. The validated T4 path had limited headroom after both models were resident, so both deployment targets should:

- serialize Stable Audio variations
- default to one generation at a time
- avoid hidden parallel generation
- show queue state in the Studio
- keep audio generation and MIDI extraction as separately observable stages
- add explicit stress tests before increasing concurrency

## Verification plan

### Desktop deployment

- Detect and display local GPU/CPU capability
- Start the Studio server on localhost
- Open the Studio in a browser
- Generate a short audio clip
- Extract MIDI from the generated clip
- Verify playback and export
- Run the same smoke path with CPU fallback
- Record startup, generation, transcription, and peak-memory metrics

### Colab T4 deployment

- Allocate a T4 session
- Install pinned dependencies
- Inject credentials ephemerally
- Start the complete Studio web app
- Verify health/readiness locally in the runtime
- Create the HTTPS tunnel
- Open the returned URL from an external browser path
- Verify frontend assets, API calls, WebSocket/streaming behavior, audio generation, MIDI extraction, and download/export
- Confirm the URL does not expose secrets or internal paths
- Stop the tunnel and Colab session
