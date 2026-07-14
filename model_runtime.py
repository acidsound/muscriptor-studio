from __future__ import annotations

import gc
import os
import re
import sys
import threading
import time
from pathlib import Path
from typing import Callable


MODEL_STABLE_AUDIO = "stabilityai/stable-audio-open-1.0"
MODEL_MUSCRIPTOR = "MuScriptor/muscriptor-medium"


class ModelRuntime:
    """Lazy Stable Audio + MuScriptor runtime for one process and one GPU."""

    def __init__(self, output_root: Path):
        self.output_root = output_root
        self._load_lock = threading.Lock()
        self._inference_lock = threading.Lock()
        self._state = "not_loaded"
        self._error: str | None = None
        self._device = "cpu"
        self._device_name = "CPU"
        self._torch_version: str | None = None
        self._stable_pipe = None
        self._muscriptor_model = None
        self._torch = None
        self._soundfile = None

    @property
    def state(self) -> str:
        return self._state

    def snapshot(self) -> dict[str, object]:
        cuda_available = False
        try:
            import torch

            cuda_available = bool(torch.cuda.is_available())
            torch_version = torch.__version__
        except Exception:
            torch_version = self._torch_version
        return {
            "model_state": self._state,
            "models": {
                "stable_audio": "loaded" if self._stable_pipe is not None else "not_loaded",
                "muscriptor": "loaded" if self._muscriptor_model is not None else "not_loaded",
            },
            "device": self._device,
            "device_name": self._device_name,
            "cuda_available": cuda_available,
            "torch_version": torch_version,
            "model_ids": {
                "stable_audio": MODEL_STABLE_AUDIO,
                "muscriptor": MODEL_MUSCRIPTOR,
            },
            "error": self._safe_error(self._error) if self._error else None,
        }

    @staticmethod
    def _safe_error(value: str | None) -> str | None:
        if not value:
            return None
        # Do not send server filesystem paths through a public HTTPS endpoint.
        value = re.sub(r"/(?:content|home|tmp)/[^\s:]+", "[path]", value)
        return value[:500]

    def _prepare_import_path(self) -> None:
        model_root = Path(os.environ.get("MUSCRIPTOR_ROOT", "/content/muscriptor"))
        if model_root.is_dir():
            root = str(model_root)
            if root in sys.path:
                sys.path.remove(root)
            sys.path.insert(0, root)
        # A stale namespace package can shadow the editable MuScriptor clone.
        for name in list(sys.modules):
            if name == "muscriptor" or name.startswith("muscriptor."):
                del sys.modules[name]

    def ensure_loaded(self, update: Callable[[str, int, str], None]) -> None:
        if self._state == "loaded":
            return
        with self._load_lock:
            if self._state == "loaded":
                return
            self._state = "loading"
            update("loading_models", 5, "Loading MuScriptor and Stable Audio models on the T4…")
            try:
                self._prepare_import_path()
                import torch
                import soundfile as sf
                from diffusers import StableAudioPipeline
                from muscriptor.transcription_model import TranscriptionModel

                self._torch = torch
                self._soundfile = sf
                self._torch_version = torch.__version__
                self._device = "cuda" if torch.cuda.is_available() else "cpu"
                self._device_name = (
                    torch.cuda.get_device_name(0) if self._device == "cuda" else "CPU"
                )
                dtype = torch.float16 if self._device == "cuda" else torch.float32

                update("loading_models", 15, "Loading MuScriptor model…")
                self._muscriptor_model = TranscriptionModel.load_model(
                    "medium", device=self._device
                )

                update("loading_models", 45, "Loading Stable Audio model…")
                token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
                if not token:
                    raise RuntimeError("HF_TOKEN is not configured in the runtime")
                self._stable_pipe = StableAudioPipeline.from_pretrained(
                    MODEL_STABLE_AUDIO,
                    torch_dtype=dtype,
                    token=token,
                ).to(self._device)
                self._stable_pipe.set_progress_bar_config(disable=True)
                self._state = "loaded"
                self._error = None
                update("loading_models", 60, f"Models ready on {self._device_name}")
            except Exception as exc:
                self._state = "error"
                self._error = f"{type(exc).__name__}: {exc}"
                self._stable_pipe = None
                self._muscriptor_model = None
                raise

    def generate_and_transcribe(
        self,
        job_id: str,
        prompt: str,
        duration_seconds: float,
        steps: int,
        seed: int,
        update: Callable[[str, int, str], None],
    ) -> dict[str, object]:
        with self._inference_lock:
            self.ensure_loaded(update)
            torch = self._torch
            sf = self._soundfile
            assert torch is not None
            assert sf is not None
            assert self._stable_pipe is not None
            assert self._muscriptor_model is not None

            job_dir = self.output_root / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            audio_path = job_dir / "audio.wav"
            midi_path = job_dir / "notes.mid"

            update("generating", 65, "Generating audio…")
            generator = torch.Generator(device=self._device).manual_seed(seed)
            started = time.perf_counter()
            with torch.inference_mode():
                output = self._stable_pipe(
                    prompt,
                    negative_prompt="low quality, clipping, noise, silence",
                    num_inference_steps=steps,
                    audio_end_in_s=duration_seconds,
                    num_waveforms_per_prompt=1,
                    generator=generator,
                ).audios
            array = output[0].T.float().cpu().numpy()
            sample_rate = int(self._stable_pipe.vae.sampling_rate)
            sf.write(audio_path, array, sample_rate)
            generation_seconds = round(time.perf_counter() - started, 3)

            update("transcribing", 82, "Extracting MIDI with MuScriptor…")
            generated_audio, generated_sr = sf.read(
                audio_path, dtype="float32", always_2d=True
            )
            mono = torch.from_numpy(generated_audio.mean(axis=1)).unsqueeze(0)
            transcribe_started = time.perf_counter()
            midi_bytes = self._muscriptor_model.transcribe_to_midi(
                (mono, generated_sr), batch_size=1, no_eos_is_ok=True
            )
            midi_path.write_bytes(midi_bytes)
            transcription_seconds = round(time.perf_counter() - transcribe_started, 3)

            return {
                "audio_url": f"/api/artifacts/{job_id}/audio.wav",
                "midi_url": f"/api/artifacts/{job_id}/notes.mid",
                "audio_bytes": audio_path.stat().st_size,
                "midi_bytes": midi_path.stat().st_size,
                "sample_rate": sample_rate,
                "duration_seconds": round(len(array) / sample_rate, 3),
                "generation_seconds": generation_seconds,
                "transcription_seconds": transcription_seconds,
                "seed": seed,
                "device": self._device_name,
            }

    def release(self) -> None:
        self._stable_pipe = None
        self._muscriptor_model = None
        gc.collect()
        if self._torch is not None and self._device == "cuda":
            self._torch.cuda.empty_cache()
        self._state = "not_loaded"
