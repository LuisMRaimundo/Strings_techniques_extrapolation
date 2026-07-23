"""Prior registry tests."""

from __future__ import annotations

from string_technique_model.extrapolation.nonlinear.priors import get_prior, load_priors


def test_priors_load() -> None:
    priors = load_priors()
    assert len(priors) >= 5
    ids = {p.prior_id for p in priors}
    assert "alpha_t_sul_tasto" in ids
    assert "alpha_t_sul_ponticello" in ids


def test_prior_lookup() -> None:
    p = get_prior("alpha_mute_vln")
    assert p is not None
    assert p.mean is not None
    assert p.mean < 0
