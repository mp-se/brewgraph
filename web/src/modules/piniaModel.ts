/*
 * Copyright (c) 2024-2026 Magnus Persson
 * SPDX-License-Identifier: GPL-3.0-only
 */

/**
 * Public instance shape retained when Pinia unwraps a class instance into reactive state.
 * Class-private backing fields are intentionally absent from the reactive proxy.
 */
export type PiniaModel<T> = Pick<T, keyof T>
