/**
 * Public instance shape retained when Pinia unwraps a class instance into reactive state.
 * Class-private backing fields are intentionally absent from the reactive proxy.
 */
export type PiniaModel<T> = Pick<T, keyof T>
