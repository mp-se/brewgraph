# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Fetch one row per owner with a window function on SQLite and PostgreSQL."""
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, aliased


def latest_by_owner(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    session: Session,
    model: Any,
    owner_col: Any,
    owner_ids: Sequence[Any],
    *,
    extra_where: Optional[Sequence[Any]] = None,
    newest_first: bool = True,
) -> Dict[Any, Any]:
    """Return ``{owner_id: row}`` holding one row per owner.

    ``newest_first=False`` returns the oldest instead, which is what a batch's
    first gravity reading is.
    """
    if not owner_ids:
        return {}

    ordering = model.created_at.desc() if newest_first else model.created_at.asc()
    ranked = (
        select(
            model,
            func.row_number()  # pylint: disable=not-callable
            .over(partition_by=owner_col, order_by=ordering)
            .label("_rn"),
        )
        .where(owner_col.in_(list(owner_ids)))
    )
    for clause in extra_where or ():
        ranked = ranked.where(clause)

    sub = ranked.subquery()
    rank_col = sub.c["_rn"]
    entity = aliased(model, sub)
    rows = session.execute(select(entity).where(rank_col == 1)).all()
    return {getattr(row[0], owner_col.key): row[0] for row in rows}


def count_by_owner(
    session: Session,
    owner_col: Any,
    owner_ids: Sequence[Any],
    *,
    extra_where: Optional[Sequence[Any]] = None,
) -> Dict[Any, int]:
    """Return ``{owner_id: count}``, with owners having no rows simply absent."""
    if not owner_ids:
        return {}

    query: Select = (
        select(owner_col, func.count())  # pylint: disable=not-callable
        .where(owner_col.in_(list(owner_ids)))
        .group_by(owner_col)
    )
    for clause in extra_where or ():
        query = query.where(clause)
    return dict(session.execute(query).all())


def group_by_owner(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    session: Session,
    model: Any,
    owner_col: Any,
    owner_ids: Sequence[Any],
    *,
    extra_where: Optional[Sequence[Any]] = None,
    order_by: Optional[Any] = None,
) -> Dict[Any, List[Any]]:
    """Return ``{owner_id: [rows]}`` for every owner, in one query.

    Used where the dashboard wants a whole short list per entity — prediction
    history — rather than a single latest row.
    """
    if not owner_ids:
        return {}

    query = select(model).where(owner_col.in_(list(owner_ids)))
    for clause in extra_where or ():
        query = query.where(clause)
    if order_by is not None:
        query = query.order_by(order_by)

    grouped: Dict[Any, List[Any]] = {}
    for row in session.scalars(query).all():
        grouped.setdefault(getattr(row, owner_col.key), []).append(row)
    return grouped
