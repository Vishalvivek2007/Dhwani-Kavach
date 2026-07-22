"""W2VAASIST-cotrain neural detector (Codecfake vendor model) -- the
strongest neural layer, when its checkpoint is present.

Weights (`models/w2v2aasist_cotrain.pt`) load into the vendored W2VAASIST head
(ml/vendor/codecfake_model.py). Preprocessing mirrors Codecfake's own
generate_score.py exactly: repeat-pad (tile) to 64600 samples at 16 kHz,
zero-mean/unit-variance normalize (Wav2Vec2FeatureExtractor's do_normalize),
run through facebook/wav2vec2-xls-r-300m, take hidden_states[5], reshape to
(1, 1, 1024, T) and feed the head.

Unlike ml/wav2vec2_detector.py, the SSL backbone here is NOT baked into the
checkpoint -- w2v2aasist_cotrain.pt only holds the W2VAASIST head. The first
call loads facebook/wav2vec2-xls-r-300m (~1.2 GB) via transformers, so
infer()/embed() need network access or a populated HF cache even once
available() is True.
"""
import math
import os
import sys
import types
import numpy as np
import torch

from ml.audio_utils import repeat_pad
from ml.vendor import codecfake_model
from ml.vendor.codecfake_model import W2VAASIST

_CKPT_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "w2v2aasist_cotrain.pt")
# DHWANI_HEAD lets you A/B a freshly trained head (e.g. w2v2aasist_robust.safetensors)
# via backend/eval WITHOUT overwriting the deployed cotrain head. Unset -> default.
_ST_PATH = os.environ.get("DHWANI_HEAD") or os.path.join(
    os.path.dirname(__file__), "..", "models", "w2v2aasist_cotrain.safetensors")
# A FULL fine-tuned bundle (backbone.* + head.*) from training/train_robust.py.
# When present it overrides BOTH the stock XLS-R backbone AND the head -- required
# because train_robust fine-tunes the backbone, so a head-only checkpoint would
# drop the gains that live in the backbone. Deploy = drop the file at the default
# path (or set DHWANI_MODEL). Takes precedence over _ST_PATH / _CKPT_PATH.
_BUNDLE_PATH = os.environ.get("DHWANI_MODEL") or os.path.join(
    os.path.dirname(__file__), "..", "models", "w2v2aasist_full.safetensors")
_WAV2VEC2_BASE_ID = "facebook/wav2vec2-xls-r-300m"  # fixed by LL = Linear(1024, 128) in W2VAASIST
_HIDDEN_LAYER = 5    # generate_score.py: model(input_values).hidden_states[5]
_CUT = 64600         # generate_score.py: pad_dataset()'s cut length

_backbone = None
_head = None

# Rollback switch: set DHWANI_DISABLE_V2=1 to force ml/detector.py's precedence
# chain (detector_v2 > wav2vec2_detector > spectrogram_cnn > aasist) to skip
# this detector entirely and fall back to wav2vec2_detector.py, without moving
# or deleting any model file. Unset (default) -> unchanged behaviour.
_DISABLED = os.environ.get("DHWANI_DISABLE_V2", "").strip().lower() in ("1", "true", "yes", "on")


def _bundle() -> str | None:
    """Path to the full fine-tuned bundle if it exists, else None."""
    return _BUNDLE_PATH if os.path.exists(_BUNDLE_PATH) else None


def available() -> bool:
    if _DISABLED:
        return False
    return _bundle() is not None or os.path.exists(_ST_PATH) or os.path.exists(_CKPT_PATH)


_CONFIG_JSON = os.path.join(os.path.dirname(__file__), "..", "models", "xlsr_300m_config.json")


def _stock_or_config_model():
    """Wav2Vec2Model to overlay weights on. When the fine-tuned bundle exists we
    only need the ARCHITECTURE (every weight gets overwritten), so build it from
    the vendored config -- zero network. from_pretrained is only for the
    fallback path that genuinely needs stock XLS-R weights; if the network is
    down it retries against the local HF cache instead of crashing the backend
    (a bank deployment must not need huggingface.co reachable to boot)."""
    from transformers import Wav2Vec2Config, Wav2Vec2Model
    if os.path.exists(_BUNDLE_PATH):
        return Wav2Vec2Model(Wav2Vec2Config.from_json_file(_CONFIG_JSON))
    try:
        return Wav2Vec2Model.from_pretrained(_WAV2VEC2_BASE_ID)
    except Exception:
        return Wav2Vec2Model.from_pretrained(_WAV2VEC2_BASE_ID, local_files_only=True)


def _get_backbone():
    global _backbone
    if _backbone is None:
        m = _stock_or_config_model()
        # We only consume hidden_states[5], so the remaining ~18 encoder layers
        # are pure wasted compute per window. Keep the first _HIDDEN_LAYER layers
        # and neutralize the trailing (stable-)layer_norm so last_hidden_state ==
        # the old hidden_states[5] *exactly* (verified bit-identical, max|delta|=0
        # over random probes; see tools/export_onnx.py). ~2-3x fewer transformer
        # layers per forward, zero change to any score/embedding.
        m.encoder.layers = torch.nn.ModuleList(list(m.encoder.layers[:_HIDDEN_LAYER]))
        m.encoder.layer_norm = torch.nn.Identity()
        m.config.output_hidden_states = False
        b = _bundle()
        if b:
            # overwrite stock XLS-R weights with the fine-tuned backbone. Same
            # truncated architecture RobustDetector trained, so keys align exactly.
            from safetensors.torch import load_file
            sd = load_file(b)
            m.load_state_dict({k[len("backbone."):]: v for k, v in sd.items() if k.startswith("backbone.")})
        m.eval()
        _backbone = m
    return _backbone


def _alias_vendored_classes_as_model_module() -> None:
    """w2v2aasist_cotrain.pt was saved with torch.save(model, ...) -- Codecfake's
    own generate_score.py convention (ADD_model = torch.load(feat_model_path)),
    which pickles the class by its *original* import path, "model.W2VAASIST"
    (their model.py, imported as a top-level "model" module during training).
    We vendored that class under ml.vendor.codecfake_model instead, so unpickling
    fails with ModuleNotFoundError: No module named 'model' unless we point that
    name at our vendored classes first.
    """
    if "model" in sys.modules:
        return
    fake = types.ModuleType("model")
    for name in ("W2VAASIST", "GraphAttentionLayer", "HtrgGraphAttentionLayer",
                 "GraphPool", "Residual_block"):
        setattr(fake, name, getattr(codecfake_model, name))
    sys.modules["model"] = fake


def _get_head() -> W2VAASIST:
    global _head
    if _head is None:
        b = _bundle()
        if b:
            # head.* tensors from the full fine-tuned bundle (paired with the
            # fine-tuned backbone loaded in _get_backbone).
            from safetensors.torch import load_file
            sd = load_file(b)
            m = W2VAASIST()
            m.load_state_dict({k[len("head."):]: v for k, v in sd.items() if k.startswith("head.")})
        elif os.path.exists(_ST_PATH):
            # Safe path: pure tensors, no pickle, no sys.modules alias. Produced by
            # tools/to_safetensors.py from the pickled checkpoint (verified to
            # round-trip). This is the preferred path -- unpickling an arbitrary
            # nn.Module (below) runs code at load time and is an RCE vector.
            from safetensors.torch import load_file
            m = W2VAASIST()
            m.load_state_dict(load_file(_ST_PATH))
        else:
            # Legacy fallback: the pickled-module checkpoint. Kept only so a
            # deployment that still has just the .pt keeps working. Run
            # tools/to_safetensors.py once and this branch is never taken.
            _alias_vendored_classes_as_model_module()
            obj = torch.load(_CKPT_PATH, map_location="cpu", weights_only=False)
            if isinstance(obj, torch.nn.Module):
                m = obj
            else:
                state = obj
                if isinstance(state, dict) and "model" in state:
                    state = state["model"]
                elif isinstance(state, dict) and "state_dict" in state:
                    state = state["state_dict"]
                m = W2VAASIST()
                m.load_state_dict(state)
        m.eval()
        _head = m
    return _head


def _zero_mean_unit_var(x: np.ndarray) -> np.ndarray:
    """Wav2Vec2FeatureExtractor(do_normalize=True) has no learnable params --
    this is exactly what processor(waveform, ...).input_values computes."""
    return (x - x.mean()) / np.sqrt(x.var() + 1e-7)


def _run(audio: np.ndarray):
    # Match generate_score.py: repeat-pad (tile) to 64600, NOT zero-pad.
    padded = repeat_pad(audio, length=_CUT).astype(np.float32)
    normed = _zero_mean_unit_var(padded)
    x = torch.from_numpy(normed).unsqueeze(0)  # (1, 64600)

    with torch.no_grad():
        # Truncated backbone: last_hidden_state == the old hidden_states[5]
        # (see _get_backbone). Same tensor, ~2-3x less compute.
        hidden = _get_backbone()(x).last_hidden_state            # (1, T, 1024)
        w2v2 = hidden.unsqueeze(dim=0).transpose(2, 3)            # (1, 1, 1024, T)
        last_hidden, logits = _get_head()(w2v2)
        # index 1 = spoof probability, matching aasist_model.py / wav2vec2_detector.py.
        # generate_score.py itself reads softmax(...)[:, 0] as its "CM score"
        # (ASVspoof-toolkit convention: score ~ P(bonafide), used for EER), but
        # its own dataset.py labels bonafide=0/spoof=1 -- the same convention
        # this codebase's other two detectors already use at index 1.
        prob = torch.softmax(logits, dim=1)[0, 1].item()

    return last_hidden[0], float(prob)


def infer(audio: np.ndarray) -> float:
    """Return spoof probability in [0, 1]; higher = more likely fake."""
    _, prob = _run(audio)
    return prob


def infer_batch(audios: list[np.ndarray]) -> list[float]:
    """Spoof probabilities for several windows in ONE forward pass.

    The upload path scores multiple chunks per call; running them as a batch
    amortizes the backbone forward instead of paying it per chunk. Equivalent to
    [infer(a) for a in audios] -- the head's BatchNorm uses running stats in eval
    mode, so items don't interact (verified bit-identical vs per-item)."""
    if not audios:
        return []
    normed = np.stack([_zero_mean_unit_var(repeat_pad(a, length=_CUT)) for a in audios]).astype(np.float32)
    x = torch.from_numpy(normed)                             # (B, 64600)
    with torch.no_grad():
        hidden = _get_backbone()(x).last_hidden_state        # (B, T, 1024)
        w2v2 = hidden.unsqueeze(1).transpose(2, 3)           # (B, 1, 1024, T)
        _, logits = _get_head()(w2v2)
        probs = torch.softmax(logits, dim=1)[:, 1]
    return [float(p) for p in probs]


def infer_raw(audio: np.ndarray) -> tuple[float, float]:
    """Return (spoof_probability, logit) before ml.scoring.calibrate() is
    applied -- consumed by tools/fit_calibration.py to fit Platt scaling
    against a labeled devkit/real, devkit/fake set of .wav files."""
    _, prob = _run(audio)
    p = min(max(prob, 1e-6), 1.0 - 1e-6)
    logit = math.log(p / (1.0 - p))
    return prob, logit


def embed(audio: np.ndarray) -> np.ndarray:
    """L2-normalised 160-d voiceprint (W2VAASIST's pre-classifier hidden
    state) for campaign correlation. Same preprocessing as infer()."""
    last_hidden, _ = _run(audio)
    v = last_hidden.numpy().astype(np.float32)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v
