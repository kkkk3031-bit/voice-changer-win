# Simple Voice Changer (Windows)

Real-time mic voice changer with 4 effects: **Deep**, **Chipmunk**, **Robot**,
**Echo**. Pure DSP (resampling, ring modulation, delay line) — no AI models,
no GPU needed, tiny and fast.

## Run it from source (any OS with Python 3.10+)

```
pip install -r requirements.txt
python app.py
```

## Build a standalone Windows .exe

PyInstaller can't cross-compile, so this step has to run **on Windows**:

1. Copy this folder to a Windows machine.
2. Double-click `build_exe.bat` (or run it from a terminal).
3. Grab `dist\VoiceChanger.exe` — that's the finished app, no Python install
   needed to run it on other Windows machines.

## Using it as your mic in Discord / games / Zoom

The app just takes an input device and plays the processed audio to an
output device — on its own, Windows apps can't "see" that output as a
microphone. To route it into Discord etc.:

1. Install **[VB-Audio Virtual Cable](https://vb-audio.com/Cable/)** (free).
   It adds two fake devices: `CABLE Input` (a fake speaker) and
   `CABLE Output` (a fake mic).
2. In Voice Changer: set **Input** = your real microphone, **Output** =
   `CABLE Input`.
3. In Discord/Zoom/game settings: set your microphone to `CABLE Output`.
4. Press **Start** in Voice Changer, pick an effect, talk normally — the
   changed voice is what comes out the other end.

(You can still hear yourself normally through real speakers/headphones by
choosing your real output device instead of CABLE Input — just won't be
routed into other apps that way.)

## Effects

| Effect | What it does |
|---|---|
| Deep | Pitch shifted down (~0.7x) |
| Chipmunk | Pitch shifted up (~1.6x) |
| Robot | Ring modulation against a 55Hz carrier |
| Echo | Feedback delay line (~280ms, decaying repeats) |

## Files

- `dsp.py` — the actual audio effects, pure numpy/scipy, unit-testable without any audio hardware
- `app.py` — Tkinter GUI + sounddevice real-time stream, wires the UI to `dsp.py`
- `requirements.txt`, `build_exe.bat` — packaging
