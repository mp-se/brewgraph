# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""Exact Pydantic wire contracts for public device ingest endpoints."""

import math
from typing import Annotated, Any, ClassVar, Literal, Optional

from pydantic import (
    AliasChoices,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictFloat,
    model_validator,
)

# A measurement is stored as received, so a numeric field is any finite number (a numeric
# string such as "18.5" is one) and carries no range. NaN and infinity cannot be stored.
# An absent temperature unit means Celsius and an absent pressure unit means kPa; a unit
# that is present must be one of its allowed values, whatever its letter case.
IngestFloat = Annotated[StrictFloat, Field(allow_inf_nan=False)]


def _optional_ingest_float(value):
    """Drop an optional value unless it is a finite JSON number."""
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) else None


OptionalIngestFloat = Annotated[Optional[float], BeforeValidator(_optional_ingest_float)]


def _upper(value):
    """Unit fields ignore letter case."""
    return value.upper() if isinstance(value, str) else value


def _pressure_unit(value):
    """Firmware spells the unit \"kPa\", \"Bar\" or \"PSI\"; store the canonical form."""
    if isinstance(value, str):
        return {"kpa": "kPa", "bar": "bar", "psi": "psi"}.get(value.lower(), value)
    return value


def _identifier(value):
    """A chip or device ID is an identifier only: a number is read as its text, and a value
    that cannot be one is ignored rather than rejected."""
    if value is None or isinstance(value, (dict, list)):
        return None
    return str(value)


_TempUnit = Annotated[Literal["C", "F"], BeforeValidator(_upper)]
_GravityUnit = Annotated[Literal["G", "P"], BeforeValidator(_upper)]
_PressureUnit = Annotated[Literal["kPa", "bar", "psi"], BeforeValidator(_pressure_unit)]
_Identifier = Annotated[Optional[str], BeforeValidator(_identifier)]


class _IngestBase(BaseModel):
    """Device protocols ignore future firmware fields but never rewrite field names."""

    model_config = ConfigDict(extra="ignore")
    dropped_fields: list[str] = Field(default_factory=list, exclude=True)
    _optional_numeric_fields: ClassVar[tuple[str, ...]] = ()

    @model_validator(mode="before")
    @classmethod
    def record_dropped_fields(cls, values):
        """Preserve names of present optional numeric fields that are discarded."""
        if not isinstance(values, dict):
            return values
        dropped = list(values.get("dropped_fields", ()))
        for field in cls._optional_numeric_fields:
            if field in values:
                value = values[field]
                if value is None or isinstance(value, bool) or not isinstance(value, (int, float)) \
                        or not math.isfinite(value):
                    dropped.append(field)
        if dropped:
            values = dict(values)
            values["dropped_fields"] = sorted(set(dropped))
        return values


class IspindelIngestRequest(_IngestBase):
    """Native iSpindel HTTP payload."""

    _optional_numeric_fields = ("angle", "temperature", "battery", "battery_percent",
                                "gravity", "RSSI")

    # The name carries the "[SG]" prefix convention that tells the service the gravity unit.
    name: Any = None
    ID: _Identifier = None
    token: Optional[str] = None
    angle: OptionalIngestFloat = None
    temperature: OptionalIngestFloat = None
    temp_units: _TempUnit = "C"
    battery: OptionalIngestFloat = None
    battery_percent: OptionalIngestFloat = None
    # A firmware or calibration fault can omit the gravity; the rest of the payload is
    # still stored so the gap stays visible instead of losing the reading.
    gravity: OptionalIngestFloat = None
    interval: Any = None
    RSSI: OptionalIngestFloat = None
    color: Any = None

    @model_validator(mode="after")
    def at_least_one_value(self) -> "IspindelIngestRequest":
        """A payload carrying no storable measurement is refused."""
        values = (self.gravity, self.angle, self.temperature, self.battery,
                  self.battery_percent, self.RSSI)
        if all(value is None for value in values):
            raise ValueError("at least one measurement is required")
        return self


class GravityIngestRequest(_IngestBase):
    """Native GravityMon HTTP payload."""

    _optional_numeric_fields = ("angle", "temperature", "battery", "battery_percent", "gravity",
                                "velocity", "rssi", "RSSI", "run-time")

    name: Any = None
    # GravityMon's HTTP-push template names these keys "ID" and "RSSI" (the iSpindel
    # convention); the lowercase spellings are accepted too.
    id: _Identifier = Field(default=None, validation_alias=AliasChoices("id", "ID"))
    token: Optional[str] = None
    angle: OptionalIngestFloat = None
    temperature: OptionalIngestFloat = None
    temp_units: _TempUnit = "C"
    battery: OptionalIngestFloat = None
    battery_percent: OptionalIngestFloat = None
    # A firmware or calibration fault can omit the gravity (absent or null); the rest of
    # the payload is still stored with a null gravity.
    gravity: OptionalIngestFloat = None
    corr_gravity: Any = Field(default=None, alias="corr-gravity")
    gravity_unit: _GravityUnit = Field(alias="gravity-unit")
    velocity: OptionalIngestFloat = None
    interval: Any = None
    rssi: OptionalIngestFloat = Field(
        default=None, validation_alias=AliasChoices("rssi", "RSSI")
    )
    run_time: OptionalIngestFloat = Field(default=None, alias="run-time")

    @model_validator(mode="after")
    def at_least_one_value(self) -> "GravityIngestRequest":
        """A payload carrying no storable measurement is refused."""
        values = (self.gravity, self.angle, self.temperature, self.battery,
                  self.battery_percent, self.rssi, self.velocity)
        if all(value is None for value in values):
            raise ValueError("at least one measurement is required")
        return self


class PressureIngestRequest(_IngestBase):
    """Native PressureMon HTTP payload."""

    _optional_numeric_fields = ("pressure", "pressure1", "pressure2", "temperature", "battery",
                                "battery_percent", "rssi", "run-time")

    model_config = {"json_schema_extra": {"examples": [{
        "token": "example-device-token", "pressure1": 14.5, "pressure2": 29.0,
        "pressure_unit": "PSI", "temperature": 68.0, "temp_unit": "F",
    }]}}

    name: Any = None
    id: _Identifier = None
    token: Optional[str] = None
    # A sensor fault can omit the pressure (absent or null); the rest of the payload is
    # still stored with a null pressure.
    pressure: OptionalIngestFloat = Field(
        default=None, validation_alias=AliasChoices("pressure", "pressure1"),
        description="First sensor: pressure or pressure1; pressure wins when both are present.",
    )
    pressure2: OptionalIngestFloat = None
    # PressureMon's HTTP-push templates name the unit keys "pressure-unit" /
    # "pressure_unit" and "temperature-unit" / "temp_unit"; "pressure_units" and
    # "temp_units" are the canonical names.
    pressure_units: _PressureUnit = Field(
        default="kPa",
        validation_alias=AliasChoices("pressure_units", "pressure-unit", "pressure_unit"),
        description=("kPa, bar or psi (case-insensitive); "
                     "pressure-unit and pressure_unit are aliases."),
    )
    temperature: OptionalIngestFloat = None
    temp_units: _TempUnit = Field(
        default="C",
        validation_alias=AliasChoices("temp_units", "temperature-unit", "temp_unit"),
        description="C or F; temperature-unit and temp_unit are aliases.",
    )
    battery: OptionalIngestFloat = None
    battery_percent: OptionalIngestFloat = None
    interval: Any = None
    rssi: OptionalIngestFloat = None
    run_time: OptionalIngestFloat = Field(default=None, alias="run-time")

    @model_validator(mode="after")
    def at_least_one_value(self) -> "PressureIngestRequest":
        """A payload carrying no storable measurement is refused."""
        values = (self.pressure, self.pressure2, self.temperature, self.battery,
                  self.battery_percent, self.rssi, self.run_time)
        if all(value is None for value in values):
            raise ValueError("at least one measurement is required")
        return self


def is_event_id(value) -> bool:
    """Whether a KegMon event id fits the pour_event.event_id column and is not blank."""
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 128


class KegmonIngestRequest(_IngestBase):
    """KegMon absolute-volume event; ``pour`` distinguishes a pour event."""

    _optional_numeric_fields = ("pour", "temperature")

    token: str = Field(min_length=1)
    pour: OptionalIngestFloat = None
    volume: IngestFloat
    maxVolume: IngestFloat
    # Celsius. Never required and never a reason to refuse the event: an unusable value is
    # dropped by the ingestion service, so it is not validated here.
    temperature: OptionalIngestFloat = None
    event_id: Optional[str] = Field(default=None, alias="eventId", max_length=128)

    @model_validator(mode="before")
    @classmethod
    def drop_unusable_event_id(cls, values):
        """Drop an event id that is not a non-blank string of at most 128 characters."""
        if not isinstance(values, dict):
            return values
        bad = [k for k in ("eventId", "event_id")
               if k in values and values[k] is not None and not is_event_id(values[k])]
        if not bad:
            return values
        values = {k: v for k, v in values.items() if k not in bad}
        values["dropped_fields"] = sorted({*values.get("dropped_fields", ()), "eventId"})
        return values


class KegmonBeerRequest(_IngestBase):
    """KegMon beer lookup request."""

    token: str = Field(min_length=1)


class KegmonBeerResponse(BaseModel):
    """Exact KegMon display response."""

    abv: Optional[float] = None
    ibu: Optional[float] = None
    ebc: Optional[float] = None
    name: Optional[str] = None


class ChamberIngestRequest(_IngestBase):
    """Snake-case chamber-controller polling contract."""

    _optional_numeric_fields = ("beer_temperature", "fridge_temperature", "rssi",
                                "battery", "battery_percent")

    token: Optional[str] = Field(default=None, min_length=1)
    id: _Identifier = None
    beer_temperature: OptionalIngestFloat = None
    fridge_temperature: OptionalIngestFloat = None
    temp_units: _TempUnit = "C"
    # Accepted for compatibility and ignored: the server computes the returned mode and
    # setpoint entirely from batch state, so what a controller reports about itself never
    # influences the answer and never causes a rejection.
    current_mode: Any = None
    current_target: Any = None
    rssi: OptionalIngestFloat = None
    # Mains-powered in practice today, but accepted for parity with the other
    # ingest contracts and any future battery-powered controller.
    battery: OptionalIngestFloat = None
    battery_percent: OptionalIngestFloat = None
    # Both optional and independent of each other; a poll with neither keeps
    # working exactly as before (server date drives step-window matching).
    # local_timestamp: naive ISO 8601, e.g. "2026-08-26T14:32:00" — the
    # device's own wall-clock reading, with no UTC offset attached.
    # timezone: IANA identifier, e.g. "America/Chicago" — used only to
    # validate that local_timestamp is a real local date; an invalid/unknown
    # identifier falls back to server-date behavior rather than erroring.
    local_timestamp: Optional[str] = None
    timezone: Optional[str] = None

    @model_validator(mode="after")
    def at_least_one_temperature(self) -> "ChamberIngestRequest":
        """A poll must carry at least one physical temperature reading."""
        if self.beer_temperature is None and self.fridge_temperature is None:
            raise ValueError("beer_temperature or fridge_temperature is required")
        return self

    @model_validator(mode="after")
    def token_or_id(self) -> "ChamberIngestRequest":
        """A poll must identify its device somehow.

        ``token`` is optional so a BLE chamber
        broadcast — which carries a chip ID and two temperatures, nothing else — can be
        bridged, matching what GravityMon and PressureMon already accept. Presence is
        still mandatory: rejecting here keeps an unidentifiable poll out of the service
        layer rather than letting it fall through to a 401.
        """
        if not self.token and not self.id:
            raise ValueError("token or id is required")
        return self


class ChamberIngestResponse(BaseModel):
    """Server control instruction returned to a chamber controller."""

    target_temperature: Optional[float] = None
    temp_units: Literal["C"] = "C"
    mode: Literal["B", "F", "R"]
