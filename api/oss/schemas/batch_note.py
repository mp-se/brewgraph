# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""BatchNote Pydantic schemas."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from oss.schemas._camel import to_camel

VALID_TEST_RESULTS = {"pass", "fail", "inconclusive"}


class BatchNoteCreate(BaseModel):
    """Used when creating a batch note."""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    content: str = Field(min_length=1, max_length=5000)
    created_at: Optional[datetime] = None
    note_type: Optional[str] = None
    test_result: Optional[str] = None

    @model_validator(mode="after")
    def _validate_test_result(self) -> "BatchNoteCreate":
        """test_result must be a known value and only set on diacetyl_test notes."""
        if self.test_result is not None and self.test_result not in VALID_TEST_RESULTS:
            raise ValueError(
                f"test_result must be one of {sorted(VALID_TEST_RESULTS)}"
            )
        if self.test_result is not None and self.note_type != "diacetyl_test":
            raise ValueError("test_result requires note_type='diacetyl_test'")
        return self


class BatchNoteUpdate(BaseModel):
    """Used when editing a batch note."""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    content: Optional[str] = Field(default=None, min_length=1, max_length=5000)
    note_type: Optional[str] = None
    test_result: Optional[str] = None

    @model_validator(mode="after")
    def _validate_test_result(self) -> "BatchNoteUpdate":
        """test_result must be a known value and only set on diacetyl_test notes."""
        if self.test_result is not None and self.test_result not in VALID_TEST_RESULTS:
            raise ValueError(
                f"test_result must be one of {sorted(VALID_TEST_RESULTS)}"
            )
        if self.test_result is not None and self.note_type != "diacetyl_test":
            raise ValueError("test_result requires note_type='diacetyl_test'")
        return self


class BatchNoteResponse(BaseModel):
    """Full batch note response including DB-assigned fields."""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: uuid.UUID
    batch_id: uuid.UUID
    content: str
    created_by: Optional[str] = None
    note_type: Optional[str] = None
    test_result: Optional[str] = None
    created_at: datetime
    updated_at: datetime
