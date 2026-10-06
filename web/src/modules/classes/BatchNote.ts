/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 * BrewGraph — https://github.com/mp-se/brewgraph
 *
 * This file is part of BrewGraph. For open source use it is licensed under
 * the GNU General Public License v3.0. For commercial use without source
 * disclosure, a separate Commercial License is required.
 * See LICENSE for details.
 */

interface BatchNoteParams {
  id?: string
  batchId?: string
  content?: string
  createdBy?: string | null
  createdAt?: string
  updatedAt?: string
}

export class BatchNote {
  private _id: string
  private _batchId: string
  private _content: string
  private _createdBy: string | null
  private _createdAt: string
  private _updatedAt: string

  constructor({
    id = '',
    batchId = '',
    content = '',
    createdBy = null,
    createdAt = '',
    updatedAt = ''
  }: BatchNoteParams = {}) {
    this._id = id
    this._batchId = batchId
    this._content = content
    this._createdBy = createdBy ?? null
    this._createdAt = createdAt
    this._updatedAt = updatedAt
  }

  get id() { return this._id }
  get batchId() { return this._batchId }
  get content() { return this._content }
  set content(v: string) { this._content = v }
  get createdBy() { return this._createdBy }
  get createdAt() { return this._createdAt }
  get updatedAt() { return this._updatedAt }

  static fromJson(data: Record<string, unknown>): BatchNote {
    return new BatchNote({
      id: String(data.id ?? ''),
      batchId: String(data.batchId ?? ''),
      content: String(data.content ?? ''),
      createdBy: data.createdBy != null ? String(data.createdBy) : null,
      createdAt: String(data.createdAt ?? ''),
      updatedAt: String(data.updatedAt ?? '')
    })
  }

  toJson(): Record<string, unknown> {
    return { content: this._content }
  }
}
