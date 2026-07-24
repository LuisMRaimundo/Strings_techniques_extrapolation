# Narrow Extrapolator GUI (LEGACY / SECONDARY)

> **LEGACY / SECONDARY.** The primary GUI is
> `Manual register → technique requests` — see
> [GUI_REFERENCE.md](GUI_REFERENCE.md). This document is retained for
> historical reference only. The obsolete claims below are preserved so
> that older screenshots can still be interpreted, but the current
> `python -m string_technique_model gui` entry point launches the
> primary GUI, not the window described here.

The desktop app is **not** an audio tool. It runs the priority-1 literature extrapolator and shows auditable numerical / qualitative cells.

Sound analysis stays in Spectral_Analyser. This GUI never imports, plays, or requires WAV/FLAC files.

## Launch (obsolete claim — primary GUI is now different)

```bash
python -m string_technique_model gui
```

> **Obsolete.** The command above now launches the *Manual register →
> technique requests* window described in
> [GUI_REFERENCE.md](GUI_REFERENCE.md). The window described below is no
> longer the default entry point.

## Main window

1. Point at evidence YAML, target grid YAML, optional research Excel (audit only), and output `.xlsx`.
2. **Run extrapolation**.
3. Filter and review cells (`value_kind`, technique, instrument).
4. **Export Excel** / open the output folder.

## What you get

- Measured ordinary EWSD reference rows
- Instrument-specific mute attenuation where curated (literature-bounded)
- Technique-specific qualitative spectral tendencies
- Explicit `unavailable` / NA when evidence is insufficient
- **No** numerical EWSD for sul tasto / sul ponticello / con sordino until a validated mapping exists

## Secondary windows (optional)

| Menu | Purpose |
|------|---------|
| Tools → Legacy recording metadata sheet… | Old row-based recording sheet (pitch/audio fields). Not required. |
| Tools → Advanced scientific tools… | Prediction / literature / developer UI. Not required. |
