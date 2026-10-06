# Web UI conventions

The shared controls in `src/ui/index.ts` and `src/components/AppButton.vue` define the default
visual and interaction contract for the OSS web UI. Prefer these controls over styling a new
Quasar or native control locally.

## Fields

- Use `AppTextInput`, `AppInputNumber`, `AppTextArea`, `AppSelect`, `AppInputDate`, and
  `AppFileUpload` for labelled form fields. They share label/help/error handling and outlined,
  dense sizing.
- For a specialized native control (for example, a table-cell editor or autocomplete), apply
  `app-native-input`; use `app-native-input--dense` only in compact contexts. This class owns
  border, focus, disabled, and sizing styles.
- Binary checkboxes/radios and purpose-built controls may use their own native or Quasar primitive.
  Keep their semantics and accessible labels explicit. The backup picker is intentionally custom
  so the user sees a clear file-selection affordance; hidden file inputs used by import buttons
  are also intentional.

## Buttons

- Use `AppButton` for actions. Set `variant` (`primary`, `secondary`, `positive`, `negative`,
  `warning`, `info`, or an outline variant) and `dense` for compact contexts; use `class` only for
  layout classes such as width or row placement.
- Use `AppRowAction` for repeated icon actions in data tables so meaning, color, density, tooltip,
  and accessible name stay consistent.
- Direct Quasar button primitives are reserved for specialized controls such as navigation menus,
  segmented toggles, and dialog close affordances. Ordinary page, form, and row actions use
  `AppButton`.

## Layout and verification

- Use `app-button-row` / `app-list-actions` for action groups and list footer placement instead of
  per-view button spacing.
- `src/ui/__tests__/uiConsistency.test.js` guards AppButton variant usage and shared styling for
  native fields. `AppButton` and `AppRowAction` tests guard their rendered variants. Run
  `npm run test:unit`, `npm run lint:check`, `npm run typecheck`, and `npm run build` before merging.
