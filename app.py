"""Simple real-time voice changer — Windows desktop app.

Captures your microphone, applies one of a few effects, and plays the result
out to a chosen output device. To use it as your mic in Discord/games/Zoom,
install a virtual audio cable (e.g. VB-Audio Virtual Cable, free) and set
this app's OUTPUT device to it, then pick "CABLE Input" as your mic in the
other app. See README.md.
"""
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
import sounddevice as sd

from dsp import PitchShifter, Echo, robot, clip

SAMPLE_RATE = 44100
BLOCK_SIZE = 2048

EFFECTS = ["Off", "Deep", "Chipmunk", "Pitch Shift", "Robot", "Echo"]


class Engine:
    """Owns the audio stream and per-effect DSP state. All effect params are
    read from plain attributes so the GUI thread can change them live without
    needing to touch the audio callback thread directly.
    """

    def __init__(self):
        self.effect = "Off"
        self.pitch_deep = 0.7
        self.pitch_chipmunk = 1.6
        self.pitch_custom = 1.0
        self.robot_hz = 55.0
        self.echo = Echo(SAMPLE_RATE)
        self._pitch_shifter = PitchShifter()
        self._robot_state = {"t": 0.0}
        self.stream = None
        self.error_queue: "queue.Queue[str]" = queue.Queue()

    def _callback(self, indata, outdata, frames, time_info, status):
        if status:
            # xruns etc. — non-fatal, just surface it once to the GUI
            self.error_queue.put(str(status))
        x = indata[:, 0]
        effect = self.effect
        if effect == "Deep":
            y = self._pitch_shifter.process(x, self.pitch_deep)
        elif effect == "Chipmunk":
            y = self._pitch_shifter.process(x, self.pitch_chipmunk)
        elif effect == "Pitch Shift":
            y = self._pitch_shifter.process(x, self.pitch_custom)
        elif effect == "Robot":
            y = robot(x, SAMPLE_RATE, self.robot_hz, self._robot_state)
        elif effect == "Echo":
            y = self.echo.process(x)
        else:
            y = x
        outdata[:, 0] = clip(y)

    def start(self, input_device, output_device):
        self.stop()
        self._pitch_shifter.reset()
        self.echo.reset()
        self._robot_state["t"] = 0.0
        self.stream = sd.Stream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            channels=1,
            dtype="float32",
            device=(input_device, output_device),
            callback=self._callback,
        )
        self.stream.start()

    def stop(self):
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Simple Voice Changer")
        self.geometry("420x420")
        self.resizable(False, False)
        self.engine = Engine()

        self._build_ui()
        self._poll_errors()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _device_lists(self):
        devices = sd.query_devices()
        inputs = [(i, d["name"]) for i, d in enumerate(devices) if d["max_input_channels"] > 0]
        outputs = [(i, d["name"]) for i, d in enumerate(devices) if d["max_output_channels"] > 0]
        return inputs, outputs

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        tk.Label(self, text="Input (microphone)").pack(anchor="w", **pad)
        self.input_var = tk.StringVar()
        self.input_combo = ttk.Combobox(self, textvariable=self.input_var, state="readonly", width=50)
        self.input_combo.pack(**pad)

        tk.Label(self, text="Output (speaker, or virtual cable for Discord/games)").pack(anchor="w", **pad)
        self.output_var = tk.StringVar()
        self.output_combo = ttk.Combobox(self, textvariable=self.output_var, state="readonly", width=50)
        self.output_combo.pack(**pad)

        self._refresh_devices()
        tk.Button(self, text="Refresh devices", command=self._refresh_devices).pack(**pad)

        tk.Label(self, text="Effect").pack(anchor="w", **pad)
        self.effect_var = tk.StringVar(value="Off")
        effect_combo = ttk.Combobox(self, textvariable=self.effect_var, values=EFFECTS, state="readonly", width=20)
        effect_combo.pack(**pad)
        effect_combo.bind("<<ComboboxSelected>>", lambda e: setattr(self.engine, "effect", self.effect_var.get()))

        self.pitch_label_var = tk.StringVar(value="Pitch Shift: 1.00x")
        tk.Label(self, textvariable=self.pitch_label_var).pack(anchor="w", **pad)
        self.pitch_var = tk.DoubleVar(value=1.0)
        pitch_scale = ttk.Scale(
            self, from_=0.5, to=2.0, orient="horizontal",
            variable=self.pitch_var, command=self._on_pitch_slide,
        )
        pitch_scale.pack(fill="x", padx=10)

        self.toggle_btn = tk.Button(self, text="Start", width=20, command=self._toggle)
        self.toggle_btn.pack(pady=16)

        self.status_var = tk.StringVar(value="Stopped")
        tk.Label(self, textvariable=self.status_var, fg="gray").pack()

    def _on_pitch_slide(self, value):
        factor = float(value)
        self.engine.pitch_custom = factor
        self.pitch_label_var.set(f"Pitch Shift: {factor:.2f}x")
        # dragging the slider previews it live, regardless of the effect dropdown
        self.effect_var.set("Pitch Shift")
        self.engine.effect = "Pitch Shift"

    def _refresh_devices(self):
        inputs, outputs = self._device_lists()
        self._input_ids = [i for i, _ in inputs]
        self._output_ids = [i for i, _ in outputs]
        self.input_combo["values"] = [f"{i}: {name}" for i, name in inputs]
        self.output_combo["values"] = [f"{i}: {name}" for i, name in outputs]
        if inputs:
            self.input_combo.current(0)
        if outputs:
            self.output_combo.current(0)

    def _toggle(self):
        if self.engine.stream is None:
            if not self.input_combo.get() or not self.output_combo.get():
                messagebox.showerror("Voice Changer", "Pick an input and output device first.")
                return
            in_idx = self._input_ids[self.input_combo.current()]
            out_idx = self._output_ids[self.output_combo.current()]
            try:
                self.engine.start(in_idx, out_idx)
            except Exception as exc:  # device busy, unsupported rate, etc.
                messagebox.showerror("Voice Changer", f"Couldn't start audio:\n{exc}")
                return
            self.toggle_btn.config(text="Stop")
            self.status_var.set("Running")
        else:
            self.engine.stop()
            self.toggle_btn.config(text="Start")
            self.status_var.set("Stopped")

    def _poll_errors(self):
        try:
            while True:
                msg = self.engine.error_queue.get_nowait()
                self.status_var.set(f"Running (warning: {msg})")
        except queue.Empty:
            pass
        self.after(500, self._poll_errors)

    def _on_close(self):
        self.engine.stop()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
