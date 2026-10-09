# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Integrity checks for executable ML model assets."""
from pathlib import Path

import pytest

from core.ml.fermentation_completion_predictor import FermentationCompletionPredictor


def test_bundled_prediction_assets_pass_integrity_check():
    """The checked-in model bundle matches the reviewed SHA-256 digests."""
    assets = Path(__file__).resolve().parents[1] / "core/ml/fermentation_completion"
    for path in assets.iterdir():
        FermentationCompletionPredictor._verify_bundled_asset(path)  # pylint: disable=protected-access


def test_tampered_bundled_named_asset_is_rejected(tmp_path):
    """Known bundled filenames are verified before pickle deserialization."""
    changed = tmp_path / "fermentation_completion.pkl"
    changed.write_bytes(b"not the reviewed model")
    with pytest.raises(ValueError, match="integrity check failed"):
        FermentationCompletionPredictor._verify_bundled_asset(changed)  # pylint: disable=protected-access


def test_unreviewed_asset_name_is_rejected(tmp_path):
    """A file with a name outside the reviewed digest list is refused, not skipped."""
    other = tmp_path / "evil.pkl"
    other.write_bytes(b"anything")
    with pytest.raises(ValueError, match="not a reviewed bundled file"):
        FermentationCompletionPredictor._verify_bundled_asset(other)  # pylint: disable=protected-access


def test_predictor_takes_no_custom_paths():
    """The constructor accepts no model, scaler or metadata path."""
    with pytest.raises(TypeError):
        FermentationCompletionPredictor(model_path="/tmp/x.pkl")  # pylint: disable=unexpected-keyword-arg


def test_predictor_loads_only_the_bundled_assets():
    """The default predictor loads from the bundled directory."""
    predictor = FermentationCompletionPredictor()
    assert predictor.model_path.parent.name == "fermentation_completion"
    assert predictor.model is not None


def test_constructor_refuses_to_deserialize_when_a_digest_does_not_match(monkeypatch):
    """A digest mismatch stops the load before any pickle is deserialized."""
    from unittest.mock import patch  # pylint: disable=import-outside-toplevel
    from core.ml import fermentation_completion_predictor as module  # pylint: disable=import-outside-toplevel

    wrong = {name: "0" * 64 for name in module._BUNDLED_ASSET_SHA256}  # pylint: disable=protected-access
    monkeypatch.setattr(module, "_BUNDLED_ASSET_SHA256", wrong)
    with patch.object(module.pickle, "loads") as loads, \
            patch.object(module.pickle, "load") as load:
        with pytest.raises(ValueError, match="integrity check failed"):
            FermentationCompletionPredictor()
    loads.assert_not_called()
    load.assert_not_called()
