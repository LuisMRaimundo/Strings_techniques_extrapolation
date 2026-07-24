# Documentation Index

This index enumerates the current documentation, states its purpose and
intended audience, and identifies the authoritative document for each subject.
All links are repository-relative and render correctly in
[StackEdit](https://stackedit.io) as well as GitHub.

## Recommended reading order

1. [../README.md](../README.md) — project overview, install and quick start.
2. [USER_GUIDE.md](USER_GUIDE.md) — end-to-end practical workflow (GUI and
   Excel outputs).
3. [GUI_REFERENCE.md](GUI_REFERENCE.md) — screen-by-screen reference for the
   primary desktop application.
4. [CLI_REFERENCE.md](CLI_REFERENCE.md) — every subcommand, argument, and
   failure mode.
5. [CONFIGURATION_REFERENCE.md](CONFIGURATION_REFERENCE.md) — YAML files under
   `configs/` and their effect on model behaviour.
6. [DATA_SCHEMA_REFERENCE.md](DATA_SCHEMA_REFERENCE.md) — record and field
   schema used by measurement, request, and result rows.
7. [EXCEL_OUTPUT_REFERENCE.md](EXCEL_OUTPUT_REFERENCE.md) — sheet and column
   dictionary for the nonlinear extrapolation workbook.
8. [NONLINEAR_EXTRAPOLATION.md](NONLINEAR_EXTRAPOLATION.md) — specialist
   companion to the technical guide, focused on the hierarchical extrapolator.
9. [TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md) — full-length technical reference,
   including formulas and provenance policies.
10. [SCIENTIFIC_LIMITATIONS.md](SCIENTIFIC_LIMITATIONS.md) — candid catalogue
    of what the software does and does not compute.
11. [GLOSSARY.md](GLOSSARY.md) — symbols, acronyms, and commonly confused
    term pairs.

## Authoritative document per subject

| Subject | Authoritative document | Notes |
|---------|------------------------|-------|
| Overall system, formulas, provenance rules | [TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md) | Full-length reference. |
| Nonlinear hierarchical extrapolation | [NONLINEAR_EXTRAPOLATION.md](NONLINEAR_EXTRAPOLATION.md) | Specialist companion; links to the technical guide for full formulas. |
| Primary GUI (manual register → requests) | [GUI_REFERENCE.md](GUI_REFERENCE.md) | Points to `src/string_technique_model/gui_metadata/extrapolator_app.py`. |
| Legacy metadata sheet GUI | [METADATA_ENTRY_GUI.md](METADATA_ENTRY_GUI.md) | Marked LEGACY / SECONDARY. |
| Legacy narrow extrapolator GUI wording | [NARROW_EXTRAPOLATION_GUI.md](NARROW_EXTRAPOLATION_GUI.md) | Marked LEGACY / SECONDARY. |
| Narrow priority-1 grid extrapolator | [NARROW_EXTRAPOLATION.md](NARROW_EXTRAPOLATION.md) | Legacy grid pipeline; kept for backward compatibility. |
| Note-level requests workflow | [NOTE_LEVEL_REQUESTS.md](NOTE_LEVEL_REQUESTS.md) | Complements the GUI reference. |
| Command-line interface | [CLI_REFERENCE.md](CLI_REFERENCE.md) | Enumerates every `argparse` subcommand. |
| Configuration files | [CONFIGURATION_REFERENCE.md](CONFIGURATION_REFERENCE.md) | Field-level guide for `configs/`. |
| Excel output layout | [EXCEL_OUTPUT_REFERENCE.md](EXCEL_OUTPUT_REFERENCE.md) | Nonlinear workbook sheets and Run_Summary keys. |
| Row and result schemas | [DATA_SCHEMA_REFERENCE.md](DATA_SCHEMA_REFERENCE.md) | `EvidenceTier`, `ValueKind`, measurement / request / result fields. |
| Scientific scope, honest caveats | [SCIENTIFIC_LIMITATIONS.md](SCIENTIFIC_LIMITATIONS.md) | Ground truth for what remains unimplemented. |
| Acoustics stress testing | [ACOUSTICS_STRESS_TESTING.md](ACOUSTICS_STRESS_TESTING.md) | Descriptor backend stress suite. |
| Symbols and terminology | [GLOSSARY.md](GLOSSARY.md) | Symbols, acronyms, confused-term pairs. |

## Purpose and intended reader

| Document | Purpose | Primary reader |
|----------|---------|----------------|
| [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md) (this file) | Route the reader to the correct document. | All users. |
| [USER_GUIDE.md](USER_GUIDE.md) | Provide a reproducible end-to-end workflow. | Doctoral researchers, composers, non-programmer users. |
| [GUI_REFERENCE.md](GUI_REFERENCE.md) | Document the primary desktop interface. | Users of the graphical workflow. |
| [CLI_REFERENCE.md](CLI_REFERENCE.md) | Document each `argparse` command exhaustively. | Command-line operators, automation pipelines. |
| [CONFIGURATION_REFERENCE.md](CONFIGURATION_REFERENCE.md) | Explain effect of each configurable field. | Maintainers, methodologists, sensitivity analysts. |
| [DATA_SCHEMA_REFERENCE.md](DATA_SCHEMA_REFERENCE.md) | Define measurement, request, and result records. | Data curators, downstream consumers. |
| [EXCEL_OUTPUT_REFERENCE.md](EXCEL_OUTPUT_REFERENCE.md) | Explain each column of exported workbooks. | Doctoral readers, audit reviewers. |
| [SCIENTIFIC_LIMITATIONS.md](SCIENTIFIC_LIMITATIONS.md) | State honest limitations. | Reviewers, thesis supervisors. |
| [GLOSSARY.md](GLOSSARY.md) | Disambiguate terminology. | All users. |
| [NONLINEAR_EXTRAPOLATION.md](NONLINEAR_EXTRAPOLATION.md) | Specialist companion to the technical guide. | Methodologists, model reviewers. |
| [TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md) | Complete technical reference. | Engineers, thesis committees. |
| [METADATA_ENTRY_GUI.md](METADATA_ENTRY_GUI.md) | Legacy secondary GUI. | Historical reference only. |
| [NARROW_EXTRAPOLATION_GUI.md](NARROW_EXTRAPOLATION_GUI.md) | Legacy GUI wording. | Historical reference only. |
| [NARROW_EXTRAPOLATION.md](NARROW_EXTRAPOLATION.md) | Legacy grid extrapolator (`extrapolate grid`). | Users of the legacy pipeline. |
| [NOTE_LEVEL_REQUESTS.md](NOTE_LEVEL_REQUESTS.md) | Note-level request workflow (`request` CLI). | GUI and CLI users. |
| [ACOUSTICS_STRESS_TESTING.md](ACOUSTICS_STRESS_TESTING.md) | Stress-testing suite for descriptor backend. | Maintainers, reviewers. |

## Reports and audit trails

The `reports/` directory contains machine-generated and human-authored audit
material. Two documents are particularly relevant to documentation quality:

- [../reports/documentation_audit.md](../reports/documentation_audit.md) —
  inventory of files inspected, corrections applied, and residual gaps.
- [../reports/scientific_limitations.md](../reports/scientific_limitations.md)
  — machine-maintained companion to `SCIENTIFIC_LIMITATIONS.md`.

## Validation

The script [../tools/validate_documentation.py](../tools/validate_documentation.py)
checks the documentation set for broken relative links, unbalanced math
delimiters, forbidden placeholders, and obsolete identifiers. Run it before
publishing changes:

```bat
python tools/validate_documentation.py
```

A non-zero exit code indicates that at least one check failed.
