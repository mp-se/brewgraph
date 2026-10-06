import { defineComponent, getCurrentInstance, h, ref, isVNode, type Component, type VNode, type VNodeChild } from 'vue'
import { QBanner, QBtn, QBtnDropdown, QCard, QCardActions, QCardSection, QDialog, QFile, QInput, QLinearProgress, QOptionGroup, QSelect, QToggle } from 'quasar'

type InputProps = { modelValue?: unknown; label?: string; help?: string; disabled?: boolean; readonly?: boolean; required?: boolean; type?: string; unit?: string; width?: string | number; badge?: number; nullable?: boolean; inline?: boolean; options?: unknown[] }
const inputProps = { modelValue: [String, Number, Boolean, Array, Object], label: String, help: String, disabled: Boolean, readonly: Boolean, required: Boolean, type: String, unit: String, width: [String, Number], badge: Number, nullable: Boolean, inline: Boolean, options: { type: Array, default: () => [] } }

// A text-like control (input, textarea, select) gets an id that its label points at, so the label
// names the control for assistive technology and a click on it focuses the field. Other content
// (radio group) labels itself. A toggle shows the label once, as the header above it, and carries
// it as its aria-label rather than repeating it beside the switch.
function formField(props: InputProps, content: VNodeChild, attrs: Record<string, unknown> = {}) {
  const labelled = props.label !== undefined && isVNode(content) && (content.type === QInput || content.type === QSelect)
  const id = labelled ? ((content as VNode).props?.for as string | undefined) ?? `app-field-${getCurrentInstance()?.uid ?? 0}` : undefined
  if (labelled) (content as VNode).props = { ...(content as VNode).props, for: id }
  return h('div', { ...attrs, class: ['app-form-field', attrs.class] }, [
    props.label !== undefined ? h('label', { class: 'app-field-label', for: id }, props.label) : null,
    props.badge ? h('span', { class: 'q-badge bg-negative text-white q-ml-sm' }, String(props.badge)) : null,
    h('div', { class: props.width === undefined ? '' : `col-${props.width}` }, [content]),
    props.help ? h('div', { class: 'app-field-help' }, props.help) : null
  ])
}

function modelInput(name: string, type?: string) {
  return defineComponent({
    name, inheritAttrs: false, props: inputProps, emits: ['update:modelValue'],
    setup(props: InputProps, { emit, attrs }) {
      const revealPassword = ref(false)
      const updateModel = (value: unknown) => {
        if (type === 'number' && props.nullable && value === '') {
          emit('update:modelValue', null)
          return
        }
        if (type === 'number' && typeof value === 'string' && value.trim() !== '') {
          const number = Number.parseFloat(value)
          emit('update:modelValue', Number.isNaN(number) ? value : number)
        } else emit('update:modelValue', value)
      }
      return () => formField(props, h(QInput, {
        ...attrs, modelValue: props.modelValue ?? '', type: props.type === 'password' && revealPassword.value ? 'text' : type ?? props.type ?? 'text', disable: props.disabled, readonly: props.readonly, required: props.required, dense: true, outlined: true, hideBottomSpace: true, 'onUpdate:modelValue': updateModel
      }, props.type === 'password'
        ? { append: () => h(QBtn, { flat: true, dense: true, round: true, icon: revealPassword.value ? 'visibility_off' : 'visibility', onClick: () => { revealPassword.value = !revealPassword.value } }) }
        : type === 'number' && props.unit ? { append: () => h('span', { class: 'app-input-unit' }, props.unit) } : undefined))
    }
  })
}

export const AppTextInput = modelInput('AppTextInput')
export const AppInputNumber = modelInput('AppNumberInput', 'number')
export const AppTextArea = defineComponent({
  name: 'AppTextArea', inheritAttrs: false, props: inputProps, emits: ['update:modelValue'],
  setup(props: InputProps, { emit, attrs }) { return () => formField(props, h(QInput, { ...attrs, modelValue: props.modelValue ?? '', type: 'textarea', autogrow: true, disable: props.disabled, readonly: props.readonly, outlined: true, dense: true, hideBottomSpace: true, 'onUpdate:modelValue': (value: unknown) => emit('update:modelValue', value) })) }
})
export const AppReadonlyInput = defineComponent({
  name: 'AppReadonlyInput', inheritAttrs: false, props: inputProps,
  setup(props: InputProps, { attrs }) { return () => formField(props, h(QInput, { ...attrs, modelValue: attrs.value ?? props.modelValue ?? '', readonly: true, borderless: true, dense: true, hideBottomSpace: true })) }
})
export const AppSelect = defineComponent({
  name: 'AppSelect', inheritAttrs: false, props: inputProps, emits: ['update:modelValue'],
  setup(props: InputProps, { emit, attrs }) { return () => formField(props, h(QSelect, { ...attrs, modelValue: props.modelValue, options: props.options, emitValue: true, mapOptions: true, disable: props.disabled || props.readonly, outlined: true, dense: true, hideBottomSpace: true, 'onUpdate:modelValue': (value: unknown) => emit('update:modelValue', value) })) }
})
export const AppRadioGroup = defineComponent({
  name: 'AppRadioGroup', inheritAttrs: false, props: inputProps, emits: ['update:modelValue'],
  setup(props: InputProps, { emit, attrs }) { return () => formField(props, h(QOptionGroup, { ...attrs, modelValue: props.modelValue, options: props.options, type: 'radio', color: 'primary', disable: props.disabled, 'onUpdate:modelValue': (value: unknown) => emit('update:modelValue', value) })) }
})
export const AppToggle = defineComponent({
  name: 'AppToggle', inheritAttrs: false, props: inputProps, emits: ['update:modelValue'],
  setup(props: InputProps, { emit, attrs }) {
    const toggle = () => h(QToggle, { 'aria-label': props.label, ...attrs, modelValue: Boolean(props.modelValue), label: props.inline ? props.label : undefined, dense: props.inline || attrs.dense, disable: props.disabled, color: 'primary', 'onUpdate:modelValue': (value: boolean) => emit('update:modelValue', value) })
    return () => props.inline ? toggle() : formField(props, toggle())
  }
})
export const AppField = defineComponent({
  name: 'AppField', inheritAttrs: false, props: inputProps,
  setup(props, { slots, attrs }) { return () => formField(props, slots.default?.({ id: attrs.id, isInvalid: Boolean(attrs.errorMessage ?? attrs['error-message']) }), attrs) }
})
export const AppCard = defineComponent({
  name: 'AppCard', inheritAttrs: false, props: { header: String, title: String, color: String, icon: [Object, String], iserr: Boolean },
  setup(props, { slots, attrs }) {
    const tone = () => props.iserr ? 'negative' : props.color ?? 'primary'
    return () => h(QCard, { ...attrs, bordered: true, flat: true, class: ['app-card', `app-card--${tone()}`, attrs.class] }, () => [props.header ? h(QCardSection, { class: ['app-card__header', `app-card__header--${tone()}`, 'text-weight-medium'] }, () => props.header) : null, h(QCardSection, () => [props.title ? h('div', { class: 'text-h6' }, [props.icon ? h(props.icon as Component, { width: 16, height: 16 }) : null, ' ', props.title]) : null, slots.default?.()])])
  }
})
export const AppMessage = defineComponent({
  name: 'AppMessage', inheritAttrs: false, props: { message: String, alert: String, dismissable: Boolean, close: Function },
  setup(props, { slots, attrs }) {
    const visible = ref(true)
    const icon = () => props.alert === 'danger' ? 'warning' : props.alert === 'warning' ? 'error_outline' : props.alert === 'success' ? 'check_circle' : 'info'
    const tone = () => props.alert === 'danger' ? 'negative' : props.alert ?? 'info'
    return () => visible.value ? h(QBanner, { ...attrs, class: ['app-message', `app-message--${tone()}`, attrs.class], inlineActions: props.dismissable }, { avatar: () => h('span', { class: 'material-icons app-message__icon', 'aria-hidden': 'true' }, icon()), default: () => [props.message ?? '', ' ', slots.default?.()], action: props.dismissable ? () => h(QBtn, { flat: true, round: true, icon: 'close', 'aria-label': 'Close', onClick: () => { visible.value = false; props.close?.(props.alert) } }) : undefined }) : null
  }
})
export const AppProgress = defineComponent({ name: 'AppProgress', inheritAttrs: false, props: { progress: { type: [Number, String], default: 0 } }, setup(props, { attrs }) { return () => h(QLinearProgress, { ...attrs, value: Math.max(0, Math.min(100, Number(props.progress) || 0)) / 100, color: 'primary', size: '20px' }) } })
export const AppFileUpload = defineComponent({
  name: 'AppFileUpload', inheritAttrs: false, props: { ...inputProps, accept: String, name: String }, emits: ['update:modelValue'],
  setup(props, { emit, attrs }) { return () => formField(props, h(QFile, { ...attrs, modelValue: props.modelValue, accept: props.accept, name: props.name, disable: props.disabled, outlined: true, dense: true, hideBottomSpace: true, 'onUpdate:modelValue': (value: File | null) => emit('update:modelValue', value) })) }
})

function dialogComponent(name: string, select = false) {
  return defineComponent({
    name, inheritAttrs: false, props: { id: String, title: String, message: String, disabled: Boolean, callback: Function, modelValue: { type: [String, Number, Boolean, Array, Object], default: null }, options: { type: Array, default: () => [] } }, emits: ['update:modelValue'],
    setup(props, { emit, attrs }) {
      const open = ref(false); const choice = ref<unknown>(props.modelValue)
      const finish = (confirmed: boolean) => { open.value = false; if (select) { if (confirmed) emit('update:modelValue', choice.value); props.callback?.(confirmed, confirmed ? choice.value : '') } else props.callback?.(confirmed) }
      return () => [h('button', { ...attrs, id: props.id, type: 'button', class: 'app-dialog-trigger', onClick: () => { choice.value = props.modelValue; open.value = true } }), h(QDialog, { modelValue: open.value, 'onUpdate:modelValue': (value: boolean) => { open.value = value } }, () => h(QCard, { class: 'app-dialog-card' }, () => [h(QCardSection, { class: 'text-h6' }, () => select && props.disabled ? 'Processing...' : props.title), h(QCardSection, () => [props.message, select ? h(QSelect, { modelValue: choice.value, options: props.options, emitValue: true, mapOptions: true, disable: props.disabled, outlined: true, 'onUpdate:modelValue': (value: unknown) => { choice.value = value } }) : null]), h(QCardActions, { align: 'right', class: 'app-dialog-actions' }, () => [h(QBtn, { label: 'Confirm', color: 'primary', disable: select && (props.disabled || choice.value === null || choice.value === undefined || choice.value === ''), onClick: () => finish(true) }), h(QBtn, { label: 'Cancel', flat: true, onClick: () => finish(false) })])]))]
    }
  })
}
export const AppConfirmDialog = dialogComponent('AppConfirmDialog')
export const AppSelectDialog = dialogComponent('AppSelectDialog', true)
export const AppDataDialog = defineComponent({
  name: 'AppDataDialog', inheritAttrs: false, props: { modelValue: [String, Number, Boolean, Array, Object], title: String, button: String, disabled: Boolean }, emits: ['click'],
  setup(props, { emit, attrs }) {
    const open = ref(false)
    return () => [
      h(QBtn, { ...attrs, label: props.button, disable: props.disabled, onClick: () => { emit('click'); open.value = true } }),
      h(QDialog, { modelValue: open.value, 'onUpdate:modelValue': (value: boolean) => { open.value = value } }, () =>
        h(QCard, { class: 'app-dialog-card' }, () => [
          h(QCardSection, { class: 'row items-center' }, () => [
            h('div', { class: 'text-h6' }, props.title),
            h(QBtn, { flat: true, round: true, icon: 'close', class: 'q-ml-auto', onClick: () => { open.value = false } })
          ]),
          h(QCardSection, () => h('pre', String(props.modelValue ?? '')))
        ])
      )
    ]
  }
})
export const AppDropdown = defineComponent({ name: 'AppDropdown', props: { label: String, disabled: Boolean }, setup(props, { slots }) { return () => h(QBtnDropdown, { label: props.label, disable: props.disabled }, () => slots.default?.()) } })

export const logDebug = (...args: unknown[]) => { if (import.meta.env.VITE_APP_DEBUG) console.log('Debug', ...args) }
export const logInfo = (...args: unknown[]) => { if (import.meta.env.VITE_APP_DEBUG) console.log('Info', ...args) }
export const logError = (...args: unknown[]) => console.log('Error', ...args)
export function isValidJson(value: string): boolean { try { JSON.parse(value); return true } catch { return false } }
export function isValidFormData(value: unknown): value is FormData { return value instanceof FormData }
export function isValidMqttData(value: unknown): boolean { return typeof value === 'object' && value !== null }
export function validateCurrentForm(form?: HTMLFormElement | null): boolean { const forms = form ? [form] : Array.from(document.querySelectorAll<HTMLFormElement>('form.app-validation')); return forms.every(current => { current.classList.add('was-validated'); return current.checkValidity() }) }
export function formatTime(value: number): string { let seconds = Math.max(0, Math.floor(value)); const units: Array<[string, number]> = [['d', 86400], ['h', 3600], ['m', 60], ['s', 1]]; const result: string[] = []; for (const [label, size] of units) { const amount = Math.floor(seconds / size); if (amount > 0) result.push(`${amount}${label}`); seconds %= size }; return result.join(' ') || '0s' }
