# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""Exact Pydantic wire contracts for public device ingest endpoints."""

from typing import Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from core.enums import DeviceColor


class _IngestBase(BaseModel):
    """Device protocols ignore future firmware fields but never rewrite field names."""

    model_config = ConfigDict(extra="ignore")


class IspindelIngestRequest(_IngestBase):
    """Native iSpindel HTTP payload."""

    name: str
    ID: Optional[int] = None
    token: Optional[str] = None
    angle: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    temperature: Optional[float] = None
    temp_units: Literal["C", "F"] = "C"
    battery: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    gravity: float = Field(ge=0.0, le=35.0)
    interval: Optional[int] = Field(default=None, ge=0)
    RSSI: Optional[int] = None
    color: Optional[DeviceColor] = None


class GravityIngestRequest(_IngestBase):
    """Native GravityMon HTTP payload."""

    name: str
    # GravityMon's HTTP-push template names these keys "ID" and "RSSI" (the iSpindel
    # convention); the lowercase spellings are accepted too.
    id: Optional[str] = Field(default=None, validation_alias=AliasChoices("id", "ID"))
    token: Optional[str] = None
    angle: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    temperature: Optional[float] = None
    temp_units: Literal["C", "F"] = "C"
    battery: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    gravity: float = Field(ge=0.0, le=35.0)
    corr_gravity: Optional[float] = Field(default=None, alias="corr-gravity")
    gravity_unit: Literal["G", "P"] = Field(alias="gravity-unit")
    velocity: Optional[float] = Field(default=None, ge=-100.0, le=100.0)
    interval: Optional[int] = Field(default=None, ge=0)
    rssi: Optional[int] = Field(default=None, validation_alias=AliasChoices("rssi", "RSSI"))
    run_time: Optional[float] = Field(default=None, ge=0.0, alias="run-time")


class PressureIngestRequest(_IngestBase):
    """Native PressureMon HTTP payload."""

    name: str
    id: Optional[str] = None
    token: Optional[str] = None
    pressure: float = Field(ge=0.0, le=3000.0)
    # PressureMon's HTTP-push template names the unit keys "pressure-unit" and
    # "temperature-unit"; the underscore spellings are accepted too.
    pressure_units: Literal["kPa", "bar", "psi"] = Field(
        validation_alias=AliasChoices("pressure_units", "pressure-unit")
    )
    temperature: Optional[float] = Field(default=None, ge=-50.0, le=212.0)
    temp_units: Literal["C", "F"] = Field(
        default="C", validation_alias=AliasChoices("temp_units", "temperature-unit")
    )
    battery: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    interval: Optional[int] = Field(default=None, ge=0)
    rssi: Optional[int] = None
    run_time: Optional[float] = Field(default=None, ge=0.0, alias="run-time")


class KegmonIngestRequest(_IngestBase):
    """KegMon absolute-volume event; ``pour`` distinguishes a pour event."""

    token: str = Field(min_length=1)
    pour: Optional[float] = Field(default=None, ge=0.0)
    volume: float = Field(ge=0.0)
    maxVolume: float = Field(ge=0.0)
    event_id: Optional[str] = Field(default=None, alias="eventId", max_length=128)


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

    token: Optional[str] = Field(default=None, min_length=1)
    id: Optional[str] = None
    beer_temperature: Optional[float] = Field(default=None, ge=-50.0, le=212.0)
    fridge_temperature: Optional[float] = Field(default=None, ge=-50.0, le=212.0)
    temp_units: Literal["C", "F"] = "C"
    # Optional: the server computes the returned mode entirely from batch state
    # (`resolve_chamber_mode`), so a controller's self-reported mode never influences
    # the answer. Requiring it would force producers that genuinely have no mode — a
    # BLE bridge sees a broadcast of two temperatures — to invent a placeholder, which
    # is a claim about hardware rather than a missing field. Still accepted and still
    # validated when sent.
    current_mode: Optional[Literal["B", "F", "O", "R"]] = None
    current_target: Optional[float] = None
    rssi: Optional[int] = None
    # Mains-powered in practice today, but accepted for parity with the other
    # ingest contracts and any future battery-powered controller.
    battery: Optional[float] = Field(default=None, ge=0.0, le=10.0)
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
