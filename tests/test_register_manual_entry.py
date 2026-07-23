"""Manual full-register value entry helpers."""

from __future__ import annotations

from string_technique_model.extrapolation.register_builder import (
    apply_pasted_table,
    apply_value_list,
    build_empty_register,
    build_register_from_notes,
    generate_requests_for_register,
    measured_with_values_only,
    parse_number,
    parse_pasted_note_value_table,
    parse_pasted_values,
)


def test_european_decimal_parsing() -> None:
    assert parse_number("70,623528") == 70.623528
    assert parse_number("38,554306") == 38.554306
    assert parse_number("4,816325") == 4.816325
    assert parse_number("25.885600") == 25.885600


def test_build_c3_to_c6_note_column() -> None:
    rows = build_register_from_notes("C3", "C6", "vla", "pp")
    assert rows[0]["note"] == "C3"
    assert rows[-1]["note"] == "C6"
    assert len(rows) == 37  # inclusive chromatic


def test_user_49_values_fit_c2_to_c6() -> None:
    text = """
70,623528
38,554306
42,287864
38,719126
35,503268
27,795461
25,885600
36,879891
30,695905
34,793031
31,173848
28,988298
29,160595
24,983277
30,797650
26,037132
23,994139
16,590142
17,748366
18,556922
18,685236
25,541413
19,702604
20,634790
17,954710
13,795649
17,357882
11,619004
14,197524
17,558458
13,601809
15,145209
15,773834
12,457872
8,730382
9,191835
7,974047
8,668368
9,525356
6,586375
7,986550
5,790592
6,961116
6,907783
7,088029
4,730762
5,669511
5,274257
4,816325
"""
    values = parse_pasted_values(text)
    assert len([v for v in values if v is not None]) == 49
    assert values[0] == 70.623528
    assert values[-1] == 4.816325

    rows = build_register_from_notes("C2", "C6", "vla", "pp")
    assert len(rows) == 49
    filled, warnings = apply_pasted_table(rows, text)
    kept = measured_with_values_only(filled)
    assert len(kept) == 49
    assert kept[0]["note"] == "C2"
    assert kept[0]["value"] == 70.623528
    assert kept[-1]["note"] == "C6"
    assert kept[-1]["value"] == 4.816325
    assert any("European" in w or "value-only" in w for w in warnings)


def test_two_column_note_value_paste_rebuilds_register() -> None:
    text = "G3\t70,623528\nG#3\t38,554306\nA3\t42,287864\n"
    notes, values, _ = parse_pasted_note_value_table(text)
    assert notes[0] == "G3"
    assert values[0] == 70.623528
    # Existing register can be empty/wrong — pasted notes must be accepted
    filled, warnings = apply_pasted_table([], text, instrument="vla", dynamic="pp")
    assert [r["note"] for r in filled] == ["G3", "G#3", "A3"]
    assert filled[0]["value"] == 70.623528
    assert any("inputted note" in w for w in warnings)


def test_build_g3_to_g7() -> None:
    rows = build_register_from_notes("G3", "G7", "vla", "pp")
    assert len(rows) == 49
    assert rows[0]["note"] == "G3"
    assert rows[-1]["note"] == "G7"


def test_generate_requests_for_all_filled_notes() -> None:
    rows = build_empty_register("vla", "pp", start_note="C3", end_note="C4")
    rows = apply_value_list(rows, [67.0 if r["note"] == "A3" else 10.0 for r in rows])
    reqs = generate_requests_for_register(rows, ["sul_tasto", "con_sordino"])
    assert len(reqs) == len(rows) * 2
