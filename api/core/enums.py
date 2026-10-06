# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Shared application enums used across models and schemas."""
from enum import Enum


class BatchStatus(str, Enum):
    """Batch lifecycle states."""

    FERMENTING = "fermenting"
    PACKAGED   = "packaged"
    ARCHIVED   = "archived"


class DryHopTriggerMethod(str, Enum):
    """Strategy for triggering a dry hop addition."""

    GRAVITY_LEVEL           = "gravity_level"
    HOURS_BEFORE_COMPLETION = "hours_before_completion"


class TemperatureFormat(str, Enum):
    """Display unit for temperature readings."""

    CELSIUS    = "c"
    FAHRENHEIT = "f"


class GravityFormat(str, Enum):
    """Display unit for gravity readings."""

    SG    = "sg"
    PLATO = "p"


class PressureFormat(str, Enum):
    """Display unit for pressure readings."""

    KPA = "kpa"
    PSI = "psi"
    BAR = "bar"


class VolumeFormat(str, Enum):
    """Display unit for volume."""

    METRIC = "metric"
    US     = "us"
    UK     = "uk"


class DeviceStatus(str, Enum):
    """Computed connectivity status for a device, derived from latest reading timestamp."""

    ACTIVE       = "active"        # reading within last 4 hours
    DISCONNECTED = "disconnected"  # no reading for >4 hours
    NEVER_SEEN   = "never_seen"    # no readings recorded


class DeviceColor(str, Enum):
    """Preset physical-device colors used consistently across the UI and BLE ingest."""

    BLACK  = "black"
    RED    = "red"
    ORANGE = "orange"
    YELLOW = "yellow"
    GREEN  = "green"
    BLUE   = "blue"
    PURPLE = "purple"
    PINK   = "pink"
    WHITE  = "white"


class DeviceBatchRole(str, Enum):
    """Role a device plays within a batch."""

    GRAVITY  = "gravity"
    PRESSURE = "pressure"
    CHAMBER  = "chamber"
    # Generic temperature probe assigned to a batch without chamber control --
    # e.g. a probe recording the fermentation's ambient temperature.
    # Distinct from CHAMBER, which implies an actively controlled setpoint.
    TEMP     = "temp"


class TempType(str, Enum):
    """What a TempReading measured, determined by the ingest path.

    Never user-entered.

    Placement (storage fridge vs fermentation room) is carried by the reading's
    vessel_id/batch_id, so it is deliberately not duplicated here.
    """

    BEER    = "beer"     # chamber controller's beer probe -- in the liquid
    CHAMBER = "chamber"  # chamber controller's fridge probe -- actively controlled air
    AMBIENT = "ambient"  # Uncontrolled ambient air


class DeviceType(str, Enum):
    """Kind of physical device, replacing the earlier free-text `software` column.

    The device types this app supports. Validity of a ``Device.device_type`` value
    is checked against ``oss.registries.device_types.device_type_registry``,
    which is populated from this enum at import time.
    """

    ISPINDEL            = "ispindel"
    GRAVITYMON          = "gravitymon"
    GRAVITYMON_GATEWAY  = "gravitymon_gateway"
    PRESSUREMON         = "pressuremon"
    CHAMBER_CONTROLLER  = "chamber_controller"
    KEGMON              = "kegmon"


class IntegrationType(str, Enum):
    """Registered account-level integration types.

    `ispindel_forward`/`brewfather_forward` carry a fixed, server-defined payload
    shape (see `oss/jobs/gravity_forward.py`). `custom_forward` renders
    `Integration.config["template"]` against a fixed `${key}` token set instead —
    the escape hatch that makes adding the next forwarding target a
    user-configured target rather than a new payload function here.
    """

    ISPINDEL_FORWARD = "ispindel_forward"
    BREWFATHER_FORWARD = "brewfather_forward"
    CUSTOM_FORWARD = "custom_forward"


class MeasurementType(str, Enum):
    """Which measurement an `Integration` forwarding target applies to.

    `ispindel_forward` requires `GRAVITY` (a hydrometer format); `brewfather_forward`
    is valid for `GRAVITY`, `PRESSURE` and `TEMP`. `custom_forward` is valid for all
    four. Each measurement has its own forwarding queue/job pair (see
    `oss/jobs/gravity_forward.py` and its pressure/pour/temp siblings).
    """

    GRAVITY  = "gravity"
    PRESSURE = "pressure"
    POUR     = "pour"
    TEMP     = "temp"


class PredictionType(str, Enum):
    """Categories of ML predictions BrewGraph can emit."""

    FERMENTATION_PROGRESS = "fermentation_progress"
    BATTERY_LOW           = "battery_low"
    KEG_EMPTY             = "keg_empty"
    WIFI_SIGNAL           = "wifi_signal"


class PredictionOutcome(str, Enum):
    """Generic outcome values shared across all prediction types.

    Fermentation-progress outcomes: FERMENTING, NEAR_DONE, DONE_SOON, COMPLETE, STALLED, UNKNOWN.
    Battery outcomes: BATTERY_OK, BATTERY_LOW, BATTERY_CRITICAL.
    Keg outcomes: KEG_OK, KEG_LOW, KEG_EMPTY.
    WiFi outcomes: WIFI_GOOD, WIFI_WEAK, WIFI_CRITICAL.
    """

    # fermentation progress
    FERMENTING  = "fermenting"
    NEAR_DONE   = "near_done"
    DONE_SOON   = "done_soon"
    COMPLETE    = "complete"
    STALLED     = "stalled"
    UNKNOWN     = "unknown"
    # battery
    BATTERY_OK       = "battery_ok"
    BATTERY_LOW      = "battery_low"
    BATTERY_CRITICAL = "battery_critical"
    # keg
    KEG_OK    = "keg_ok"
    KEG_LOW   = "keg_low"
    KEG_EMPTY = "keg_empty"
    # wifi
    WIFI_GOOD     = "wifi_good"
    WIFI_WEAK     = "wifi_weak"
    WIFI_CRITICAL = "wifi_critical"


class VesselType(str, Enum):
    """Storage vessel types."""

    KEG     = "keg"
    BOTTLES = "bottles"


class VesselStatus(str, Enum):
    """Storage vessel lifecycle states.

    Stored states (user-controlled):
      clean        - vessel is empty and sanitised, ready to fill
      filled       - vessel is filled, beer is maturing (includes conditioning —
                     see below)
      serving      - beer is ready to pour

    Computed properties (not stored):
      on_tap       - derived from tap_id IS NOT NULL
      empty        - derived from status == serving AND volume/bottles == 0
      conditioning - derived from fill_date + conditioning_days, same pattern as
                     Batch's ready_date computation; never a stored status
    """

    CLEAN        = "clean"
    FILLED       = "filled"
    SERVING      = "serving"


class IngestionSource(str, Enum):
    """What kind of data was received in an ingestion request."""

    GRAVITY  = "gravity"
    PRESSURE = "pressure"
    POUR     = "pour"
    CHAMBER  = "chamber"


class IngestionErrorReason(str, Enum):
    """Reasons an ingestion request was rejected.

    Every member here is a rejection the ingestion pipeline can actually issue;
    a reason no code path assigns does not belong in the list, because it turns
    an exhaustive match into a lie for anyone handling these values.
    """

    UNKNOWN_TOKEN       = "unknown_token"
    RATE_LIMITED_DEVICE = "rate_limited_device"
    PARSE_ERROR         = "parse_error"
    # Batch creation rejected because the account's configured active-batch
    # limit was already reached.
    BATCH_QUOTA_EXHAUSTED = "batch_quota_exhausted"
