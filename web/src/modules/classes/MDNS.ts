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

interface MDNSParams {
  host?: string
  name?: string
  type?: string
}

export class MDNS {
  private _host: string
  private _name: string
  private _type: string

  constructor({ host = '', name = '', type = '' }: MDNSParams = {}) {
    this._host = host
    this._name = name
    this._type = type
  }

  static fromJson(m: Record<string, unknown>): MDNS {
    return new MDNS({
      host: m.host as string,
      name: m.name as string,
      type: m.type as string
    })
  }

  toJson(): Record<string, unknown> {
    return { host: this.host, name: this.name, type: this.type }
  }

  get host() {
    return this._host
  }
  get name() {
    return this._name
  }
  get type() {
    return this._type
  }

  set host(v: string) {
    this._host = v
  }
  set name(v: string) {
    this._name = v
  }
  set type(v: string) {
    this._type = v
  }
}
