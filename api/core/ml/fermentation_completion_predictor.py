# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Fermentation completion predictor using a trained ML model."""


import hashlib
import hmac
import json
import logging
import pickle
from datetime import datetime
from pathlib import Path

import numpy as np


logger = logging.getLogger(__name__)

# Model files are executable pickle payloads.  These digests make an accidental or
# volume-level replacement fail closed before deserialization.  Releasing a new model
# requires deliberately updating the matching digest in the reviewed source change.
_BUNDLED_ASSET_SHA256 = {
    "fermentation_completion.pkl": (
        "e2c1839137528a94539c327ff3926f3f50859ceeab2b0e1a4d9c4420bb24f408"
    ),
    "fermentation_completion_scaler.pkl": (
        "a8ce4dad95e7190950e874372245face069c40f2d8a3f54f6d69e3ad6bd26763"
    ),
    "fermentation_completion_metadata.json": (
        "d28b3809393ee734c25b3cb82c39ca289a0e276f2416dae5a5c1968dcabf477a"
    ),
}


class FermentationCompletionPredictor:
    """
    Python implementation of the BrewGraph fermentation completion predictor.
    Matches the logic used in the ESP32 C++ implementation and training pipeline.
    """

    def __init__(self, model_path=None, scaler_path=None, metadata_path=None):
        assets = Path(__file__).resolve().parent / 'fermentation_completion'

        self.model_path = (
            Path(model_path) if model_path else assets / 'fermentation_completion.pkl'
        )
        self.scaler_path = (
            Path(scaler_path) if scaler_path else assets / 'fermentation_completion_scaler.pkl'
        )
        self.metadata_path = (
            Path(metadata_path)
            if metadata_path
            else assets / 'fermentation_completion_metadata.json'
        )

        self.model = None
        self.scaler = None
        self.metadata = None

        self._load_assets()

    @staticmethod
    def _verify_bundled_asset(path: Path) -> None:
        """Reject a changed bundled model asset before opening executable pickle.

        Known production asset names are always checked, including when tests or an
        operator provide an alternate path with one of those names.  An explicitly
        named third-party model is outside this bundled-asset contract.
        """
        expected = _BUNDLED_ASSET_SHA256.get(path.name)
        if expected is None:
            return
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if not hmac.compare_digest(digest, expected):
            raise ValueError(f"Model asset integrity check failed: {path.name}")

    def _load_assets(self):
        """Load the trained model, scaler, and metadata."""
        try:
            self._verify_bundled_asset(self.model_path)
            self._verify_bundled_asset(self.scaler_path)
            self._verify_bundled_asset(self.metadata_path)
            with open(self.model_path, 'rb') as f:
                self.model = pickle.load(f)

            with open(self.scaler_path, 'rb') as f:
                self.scaler = pickle.load(f)

            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                self.metadata = json.load(f)

            logger.info("Loaded fermentation model from %s", self.model_path.name)
        except Exception as exc:
            logger.error("Error loading fermentation model assets: %s", exc)
            raise

    def calculate_features(  # pylint: disable=too-many-arguments,too-many-locals,too-many-positional-arguments
            self, history, current_gravity, current_temp,
            start_gravity, plateau_gravity, hours_elapsed,
            og=None, yeast_temp_min=15.0, yeast_temp_max=22.0,
            yeast_temp_optimal_min=None, yeast_temp_optimal_max=None,
            yeast_attenuation_min=72.0, yeast_attenuation_max=80.0,
            is_lager=0):
        """
        Calculate features matching the training pipeline logic.

        Args:
            history: List of (timestamp, gravity, temp) tuples for velocity calculation
            current_gravity: Current specific gravity
            current_temp: Current temperature in Celsius
            start_gravity: Initial gravity at start of fermentation
            plateau_gravity: Expected or target plateau gravity (FG)
            hours_elapsed: Hours since fermentation start
            og: Original gravity (defaults to start_gravity)
            yeast_temp_min: Yeast minimum temperature
            yeast_temp_max: Yeast maximum temperature
            yeast_temp_optimal_min: Yeast optimal temp lower bound (defaults to yeast_temp_min)
            yeast_temp_optimal_max: Yeast optimal temp upper bound (defaults to yeast_temp_max)
            yeast_attenuation_min: Yeast minimum attenuation %
            yeast_attenuation_max: Yeast maximum attenuation %
            is_lager: 1 if lager yeast, 0 otherwise

        Returns:
            np.array: Scaled feature vector
        """
        og = og or start_gravity
        opt_lo = yeast_temp_optimal_min if yeast_temp_optimal_min is not None else yeast_temp_min
        opt_hi = yeast_temp_optimal_max if yeast_temp_optimal_max is not None else yeast_temp_max

        # 1. gravity_drop
        gravity_drop = start_gravity - current_gravity

        # 2. gravity_drop_rate
        gravity_drop_rate = gravity_drop / max(hours_elapsed, 1.0)

        # 3. drop_velocity_6h & temp_velocity_6h
        velocity_6h = 0.0
        temp_velocity_6h = 0.0
        if history and len(history) > 1:
            now_ts = history[-1][0]
            for i in range(len(history) - 2, -1, -1):
                item = history[i]
                ts = item[0]
                time_diff = (now_ts - ts).total_seconds() / 3600
                if time_diff >= 6.0:
                    grav = item[1]
                    velocity_6h = (grav - current_gravity) / time_diff
                    if len(item) > 2:
                        prev_temp = item[2]
                        temp_velocity_6h = (current_temp - prev_temp) / time_diff
                    break

        # 4. fermentation_progress
        total_expected_drop = start_gravity - plateau_gravity
        fermentation_progress = 0.0
        if total_expected_drop > 0:
            fermentation_progress = min(max(gravity_drop / total_expected_drop, 0.0), 1.0)

        # 5. temp_corrected_rate (Q10=2.0, ref=20°C)
        temp_corrected_rate = 0.0
        if gravity_drop_rate > 0:
            temp_correction = 2.0 ** ((current_temp - 20.0) / 10.0)
            temp_corrected_rate = gravity_drop_rate / temp_correction

        # 6. temp_deviation_from_yeast (°C outside optimal range)
        if current_temp < opt_lo:
            temp_deviation = opt_lo - current_temp
        elif current_temp > opt_hi:
            temp_deviation = current_temp - opt_hi
        else:
            temp_deviation = 0.0

        # 7. gravity_range
        gravity_range = og - plateau_gravity

        # Build 14-feature vector (order must match training pipeline)
        features = np.array([[
            gravity_drop,
            gravity_drop_rate,
            velocity_6h,
            temp_velocity_6h,
            temp_corrected_rate,
            fermentation_progress,
            yeast_temp_min,
            yeast_temp_max,
            yeast_attenuation_min,
            yeast_attenuation_max,
            temp_deviation,
            og,
            gravity_range,
            is_lager,
        ]])

        return self.scaler.transform(features)

    def predict(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-return-statements
            self, history, current_gravity, current_temp,
            start_gravity, plateau_gravity, hours_elapsed,
            og=None, yeast_temp_min=None, yeast_temp_max=None,
            yeast_temp_optimal_min=None, yeast_temp_optimal_max=None,
            yeast_attenuation_min=None, yeast_attenuation_max=None,
            is_lager=0):
        """
        Predict hours remaining until fermentation completion.

        Yeast parameters (yeast_temp_min/max, attenuation_min/max) must be
        provided — returns None until yeast data has been fetched.

        Returns:
            float: Estimated hours remaining, or None if not ready
        """
        if not history or len(history) < 2:
            return None

        # Wait until yeast data is available
        if yeast_temp_min is None or yeast_temp_max is None:
            return None
        if yeast_attenuation_min is None or yeast_attenuation_max is None:
            return None

        first_ts = history[0][0]
        last_ts = history[-1][0]
        total_window = (last_ts - first_ts).total_seconds() / 3600

        if total_window < 6.0:
            return None

        if current_gravity <= plateau_gravity:
            return 0.5

        try:
            X_scaled = self.calculate_features(  # pylint: disable=invalid-name
                history, current_gravity, current_temp,
                start_gravity, plateau_gravity, hours_elapsed,
                og=og, yeast_temp_min=yeast_temp_min, yeast_temp_max=yeast_temp_max,
                yeast_temp_optimal_min=yeast_temp_optimal_min,
                yeast_temp_optimal_max=yeast_temp_optimal_max,
                yeast_attenuation_min=yeast_attenuation_min,
                yeast_attenuation_max=yeast_attenuation_max,
                is_lager=is_lager,
            )

            prediction = self.model.predict(X_scaled)[0]
            return max(0.0, float(prediction))

        except (ValueError, RuntimeError) as e:
            print(f"⚠️ Prediction error: {e}")
            return None

if __name__ == "__main__":
    # Simple test case
    predictor = FermentationCompletionPredictor()

    # Mock history (at 15h elapsed, starting at 1.0415)
    now = datetime.now()
    sample_history = [
        (now.replace(hour=now.hour - 15), 1.0415, 18.5), # Start
        (now.replace(hour=now.hour - 9), 1.0350, 19.8),  # 6h gap from 15h ago
        (now, 1.0310, 20.5)                              # Current
    ]

    hours_left = predictor.predict(
        history=sample_history,
        current_gravity=1.0310,
        current_temp=19.5,
        start_gravity=1.0415,
        plateau_gravity=1.0080,
        hours_elapsed=15.0,
        og=1.0415,
        yeast_temp_min=15.0,
        yeast_temp_max=22.0,
        yeast_temp_optimal_min=18.0,
        yeast_temp_optimal_max=22.0,
        yeast_attenuation_min=73.0,
        yeast_attenuation_max=80.0,
        is_lager=0,
    )

    if hours_left:
        print(f"📊 Predicted Completion: {hours_left:.1f} hours from now")
    else:
        print("⌛ Waiting for more data (need 6h window)...")
