# Runtime Modes

MuScriptor Studio is **local-first**. The application should remain useful on a personal desktop without requiring an account, hosted backend, or permanent remote GPU.

## Runtime policy

1. Prefer the best available local execution backend.
2. Fall back to CPU rather than making the application unusable when no GPU is present.
3. Let the user intentionally select Colab T4 when temporary or low-cost remote GPU acceleration is useful.
4. Keep projects, clips, and job payloads provider-neutral so a project can move between local and remote execution.
5. Never send credentials or private project data to a runtime without an explicit user-visible choice.

## Providers

| Provider | Role | Default | Expected behavior |
|---|---|---:|---|
| Local GPU | Primary acceleration path on a personal desktop | Yes when detected | Use the available supported GPU backend and keep models resident when practical |
| Local CPU | Compatibility fallback | Yes when no GPU is available | Preserve the same functional workflow; show that generation/transcription may be substantially slower |
| Colab T4 | Optional remote GPU provider | No | Start a temporary runtime, run the same job contract, return assets, and stop the runtime when finished |

The first implementation should prioritize CUDA-capable local GPUs and CPU fallback. Other local GPU backends, such as Apple Silicon/MPS, can use the same provider interface after model-specific validation.

## Provider-neutral job contract

The Studio UI should not know whether a job runs locally or in Colab. It should submit a provider-neutral job such as:

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

The runtime returns explicit state and assets:

```json
{
  "status": "ready",
  "provider": "local-gpu",
  "audio_asset": "...",
  "midi_asset": "...",
  "metadata": {
    "sample_rate": 44100,
    "duration_seconds": 8
  }
}
```

The exact API schema is provisional. The important boundary is that `local-gpu`, `local-cpu`, and `colab-t4` implement the same lifecycle:

```text
queued → generating → extracting-midi → ready
                                  └→ failed / cancelled
```

## Runtime selection UX

The initial Studio selector should be intentionally small:

```text
Runtime: Auto ▾
  Auto
  Local GPU
  Local CPU
  Colab T4
```

### Auto

`Auto` chooses a local GPU when supported and available, then falls back to local CPU. It does not silently switch to Colab because remote execution has privacy, latency, credential, and cost implications.

### Local GPU

Use when the user wants predictable local execution. The UI can show the detected backend and memory status in an advanced panel, but hardware details should not dominate the main Studio surface.

### Local CPU

CPU mode must remain a first-class compatibility path:

- Audio playback, timeline editing, MIDI editing, and export remain local.
- Stable Audio generation and MuScriptor transcription use CPU-compatible implementations where supported.
- The UI must show an honest estimate or “may take longer” state rather than appearing frozen.
- CPU performance and maximum usable duration must be benchmarked before claiming production readiness.

CPU fallback is a product requirement, not a claim that every model configuration has already been performance-validated.

### Colab T4

Colab is an optional remote provider for users who do not have a suitable local GPU or want a reproducible temporary runtime.

The Colab provider should:

- make the remote choice explicit
- establish or reuse a named temporary session
- keep Hugging Face credentials out of the browser, project files, Drive, and logs
- run the same audio-generation and transcription job contract
- return WAV/MIDI/project assets through a controlled channel
- expose queued, running, ready, and failed states
- stop the temporary GPU session after the work is complete or cancelled

The current T4 validation supports the feasibility of the combined Stable Audio + MuScriptor path for short, batch-1 jobs. It does not establish limits for longer clips, higher inference steps, or multiple concurrent users.

## Data locality

| Data | Local GPU / CPU | Colab T4 |
|---|---|---|
| Project metadata | Local by default | Sent only for an explicit remote job |
| Prompt | Local by default | Sent with the selected remote job |
| Generated WAV/MIDI | Saved to local project | Returned and saved locally after completion |
| HF token | Local protected runtime only | Injected into the temporary runtime; never exposed to UI |
| Model cache | Local runtime cache | Temporary Colab cache |
| Raw transcript / logs | Local and private by default | Do not expose in public links or logs |

## Resource policy

GPU memory is not an unlimited concurrency pool. The validated T4 path had limited headroom after both models were resident, so the first implementation should:

- serialize Stable Audio variations
- default to one generation at a time
- avoid hidden parallel generation
- show queue state in the Studio
- keep audio generation and MIDI extraction as separately observable stages
- add explicit stress tests before increasing concurrency

## Verification plan

The runtime layer should be validated separately for each provider:

### Local GPU

- Detect device and backend
- Load Stable Audio and MuScriptor
- Generate a short audio clip
- Extract MIDI from the generated clip
- Verify playback/export
- Record load time, generation time, and peak memory

### Local CPU

- Run the same functional smoke path
- Measure startup and inference time
- Determine safe duration and memory limits
- Ensure the UI remains responsive while jobs run

### Colab T4

- Allocate a T4 session
- Install the pinned dependencies
- Inject credentials ephemerally
- Run the same smoke path
- Download/verify WAV and MIDI artifacts
- Stop the session after completion
