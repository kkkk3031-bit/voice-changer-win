"""Real-time-safe audio effects. No AI, no heavy deps — just numpy/scipy.

Every process_* function takes one fixed-size mono float32 block and returns
a block of the SAME length, so it can be called straight from a fixed-size
audio callback (sounddevice) without breaking stream timing.
"""
import numpy as np
from scipy.signal import resample


class PitchShifter:
    """Cheap real-time pitch shift: resample each block to the target pitch
    ratio, then drip-feed fixed-size output blocks from a small internal
    buffer so the stream always gets exactly `blocksize` samples back.

    factor > 1.0 -> higher pitch (chipmunk). factor < 1.0 -> lower pitch (deep).
    """

    def __init__(self):
        self._buffer = np.zeros(0, dtype=np.float32)

    def reset(self):
        self._buffer = np.zeros(0, dtype=np.float32)

    def process(self, x: np.ndarray, factor: float) -> np.ndarray:
        n = len(x)
        if factor == 1.0:
            return x.astype(np.float32)

        target_len = max(1, int(round(n / factor)))
        resampled = resample(x, target_len).astype(np.float32)
        self._buffer = np.concatenate([self._buffer, resampled])

        if len(self._buffer) >= n:
            out, self._buffer = self._buffer[:n], self._buffer[n:]
        else:
            pad = np.zeros(n - len(self._buffer), dtype=np.float32)
            out, self._buffer = np.concatenate([self._buffer, pad]), np.zeros(0, dtype=np.float32)
        return out


class Echo:
    """Simple feedback delay line."""

    def __init__(self, sample_rate: int, delay_seconds: float = 0.28, feedback: float = 0.35, mix: float = 0.5):
        self.sr = sample_rate
        self.feedback = feedback
        self.mix = mix
        self._buf = np.zeros(max(1, int(sample_rate * delay_seconds)), dtype=np.float32)
        self._pos = 0

    def reset(self):
        self._buf[:] = 0
        self._pos = 0

    def process(self, x: np.ndarray) -> np.ndarray:
        n = len(x)
        buf_len = len(self._buf)
        out = np.empty(n, dtype=np.float32)
        for i in range(n):
            idx = (self._pos + i) % buf_len
            delayed = self._buf[idx]
            out[i] = x[i] + self.mix * delayed
            self._buf[idx] = x[i] + self.feedback * delayed
        self._pos = (self._pos + n) % buf_len
        return out


def robot(x: np.ndarray, sample_rate: int, carrier_hz: float = 55.0, _phase_state: dict | None = None) -> np.ndarray:
    """Ring modulation against a fixed-frequency carrier — classic robot voice.
    `_phase_state` (a single-item dict {'t': float}) keeps the carrier phase
    continuous across blocks so there's no click at block boundaries.
    """
    n = len(x)
    t0 = _phase_state.get("t", 0.0) if _phase_state is not None else 0.0
    t = t0 + np.arange(n) / sample_rate
    carrier = np.sin(2 * np.pi * carrier_hz * t).astype(np.float32)
    if _phase_state is not None:
        _phase_state["t"] = t[-1] + 1.0 / sample_rate
    return (x * carrier).astype(np.float32)


def clip(x: np.ndarray) -> np.ndarray:
    return np.clip(x, -1.0, 1.0).astype(np.float32)
