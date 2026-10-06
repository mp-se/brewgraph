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
