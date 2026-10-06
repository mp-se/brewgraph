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

/*
 * Central API client for all store -> backend calls.
 *
 * Collapses the fetch envelope every Pinia store needs into one place:
 * auth header, content-type, request timeout, the global busy flag,
 * status checking, error logging and JSON parsing. Building the Authorization
 * header in one place means auth changes (token refresh, 401 handling) are a
 * single edit instead of one per call site.
 */
import { global } from '@/modules/pinia'
import { logDebug, logError } from '@/ui'

export interface ApiOptions {
  /** Toggle the global busy flag for the duration of the call (default true). */
  busy?: boolean
  /** Strict set of success status codes. When omitted, any 2xx (res.ok) passes. */
  okStatuses?: number[]
  /** Treat a 404 response as a successful `null` rather than an error. */
  notFoundAsNull?: boolean
  /** Skip setting global.messageError on failure (caller handles errors). */
  noErrorNotify?: boolean
}

/** Options for the raw `apiFetch`, for callers that do not fit the default envelope. */
export interface RawOptions {
  /** Prefix for `path` instead of `global.apiURL`. Pass `''` to give `path` as a full URL. */
  baseURL?: string
  /** Authorization value instead of `global.token` (the backup modules receive it as a parameter). */
  token?: string
  /** Abort signal of the caller, for a stream it cancels itself. Replaces the default timeout. */
  signal?: AbortSignal
  /** Set `false` to send without a request timeout (streams, large backup transfers). Default true. */
  timeout?: boolean
}

function buildInit(method: string, body: unknown, raw: RawOptions = {}): RequestInit {
  const hasBody = body !== undefined
  const signal =
    raw.signal ?? (raw.timeout === false ? undefined : AbortSignal.timeout(global.fetchTimout))
  return {
    method,
    headers: {
      ...(hasBody ? { 'Content-Type': 'application/json' } : {}),
      Authorization: raw.token ?? global.token
    },
    ...(hasBody ? { body: JSON.stringify(body) } : {}),
    ...(signal ? { signal } : {})
  }
}

function isOk(res: Response, okStatuses?: number[]): boolean {
  return okStatuses ? okStatuses.includes(res.status) : res.ok
}

/**
 * Turn a failed Response into a human-readable message. Every error response from this
 * API carries the normative envelope `{error, message, requestId}` (see
 * `main_oss.py`'s `validation_handler` / `http_exception_handler`) — `message` is always
 * a flat, human-readable string: a service-raised `HTTPException`'s detail verbatim (e.g.
 * the integrations SSRF check's "URL resolves to disallowed address ..."), or a generic
 * "Invalid request" for schema-level failures (the raw per-field detail is logged
 * server-side, not returned). Falls back to the status line if the body isn't JSON or
 * doesn't carry `message`.
 */
async function extractErrorDetail(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { message?: unknown }
    if (typeof body?.message === 'string' && body.message) return body.message
  } catch {
    // Body wasn't JSON (or had no usable `message`) — fall through.
  }
  return `${res.status} ${res.statusText}`.trim()
}

/**
 * Low-level request: applies the auth header, content-type and timeout, then
 * returns the raw `Response`. Status checking, body parsing and error handling
 * are the caller's responsibility. Use only for bespoke flows that the
 * `apiJson` / `apiOk` helpers cannot express (custom status branches such as
 * 424, or non-JSON bodies like blob downloads). Throws on network/timeout
 * errors, like `fetch`. `raw` overrides the base URL, token, signal and timeout for the
 * event stream and the backup modules.
 */
export function apiFetch(
  method: string,
  path: string,
  body?: unknown,
  raw: RawOptions = {}
): Promise<Response> {
  return fetch((raw.baseURL ?? global.apiURL) + path, buildInit(method, body, raw))
}

/**
 * Send a request and return the parsed JSON body, or `null` on any failure.
 * Use for GET/POST/PATCH calls that return a resource.
 */
export async function apiJson<T = unknown>(
  method: string,
  path: string,
  body?: unknown,
  opts: ApiOptions = {}
): Promise<T | null> {
  const { busy = true, okStatuses, notFoundAsNull = false, noErrorNotify = false } = opts
  const releaseBusy = busy ? global.acquireBusy() : undefined
  try {
    const res = await fetch(global.apiURL + path, buildInit(method, body))
    logDebug('apiClient', method, path, res.status)
    if (notFoundAsNull && res.status === 404) return null
    if (!isOk(res, okStatuses)) {
      const detail = await extractErrorDetail(res)
      logError('apiClient ' + method + ' ' + path, res.status, detail)
      if (!noErrorNotify) global.messageError = detail
      return null
    }
    return (await res.json()) as T
  } catch (err) {
    logError('apiClient ' + method + ' ' + path, err)
    if (!noErrorNotify) {
      global.messageError = `${method} ${path} failed`
    }
    return null
  } finally {
    releaseBusy?.()
  }
}

/**
 * Send a request and return whether it succeeded, ignoring any response body.
 * Use for DELETE (204) and fire-and-forget writes that report only success.
 */
export async function apiOk(
  method: string,
  path: string,
  body?: unknown,
  opts: ApiOptions = {}
): Promise<boolean> {
  const { busy = true, okStatuses, noErrorNotify = false } = opts
  const releaseBusy = busy ? global.acquireBusy() : undefined
  try {
    const res = await fetch(global.apiURL + path, buildInit(method, body))
    logDebug('apiClient', method, path, res.status)
    const ok = isOk(res, okStatuses)
    if (!ok && !noErrorNotify) {
      global.messageError = await extractErrorDetail(res)
    }
    return ok
  } catch (err) {
    logError('apiClient ' + method + ' ' + path, err)
    if (!noErrorNotify) {
      global.messageError = `${method} ${path} failed`
    }
    return false
  } finally {
    releaseBusy?.()
  }
}
