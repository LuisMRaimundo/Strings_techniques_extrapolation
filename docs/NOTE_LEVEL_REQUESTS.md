# Note-level requests (have → need + technique)

## Preferred: manual whole-register entry

In the GUI (`python -m string_technique_model gui`):

1. Choose instrument + dynamic → **Build empty full register**
2. Type values note-by-note, or **Paste values column** / Ctrl+V (one number per line for the whole register)
3. Select techniques → **Generate from filled register**
4. **Run requests**

You can also **Save Measured register…** / **Load Measured register…** as Excel.

## Excel columns (same model)

**Measured** (notes you have — typically the whole register):

| note | value | instrument | dynamic | technique |
|------|------:|------------|---------|-----------|
| C3   | 40    | vla        | pp      | ordinary  |
| C#3  | 41    | vla        | pp      | ordinary  |
| …    | …     | vla        | pp      | ordinary  |
| A4   | 67    | vla        | pp      | ordinary  |

**Requests** (notes you need + technique):

| note | technique        | instrument | dynamic |
|------|------------------|------------|---------|
| A4   | con_sordino      | vla        | pp      |
| A4   | sul_tasto        | vla        | pp      |
| A4   | sul_ponticello   | vla        | pp      |

## Run

```bash
python -m string_technique_model request --write-template outputs/extrapolation/request_template.xlsx
python -m string_technique_model request --workbook your_file.xlsx --output outputs/extrapolation/note_level_requests.xlsx

# Or use a Spectral_Analyser research Excel as Measured:
python -m string_technique_model request --research-excel path/to/compiled_density_metrics_research.xlsx --requests requests.xlsx --instrument vla --dynamic pp
```

GUI: `python -m string_technique_model gui` → Write template / Load / Run requests.

## Output

For each request: matched `baseline_value` for that note, plus literature effect fields (`qualitative_effect_vs_ordinary`, `attenuation_db_power` when curated). Numeric technique EWSD is only filled when a validated transform exists; otherwise `value` is NA with `na_reason`, while the ordinary baseline remains visible.
