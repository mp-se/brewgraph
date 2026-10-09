# @brewgraph/core

Shared, framework-neutral client-side domain logic for BrewGraph products.

Current modules:

- Integration payload preview and template rendering
- BeerXML parsing
- Cursor and numbered pagination helpers
- Brewing calculations and unit conversions
- Device-status field extraction and capability detection
- Device assignment eligibility and endpoint selection
- Framework-neutral record sorting
- Decimal precision helpers and schema-error summaries
- Shared API-contract integration and settings identifiers
- Moving-average telemetry filtering
- Text truncation and relative/duration time formatting
- Generic active-reading statistics
- Gravity telemetry-series transformations
- Bounded gravity-formula parsing, evaluation, calibration fitting and profile serialization
- Fermentation payload normalization
- Fermentation-step parsing, serialization, and scheduling

Do not add Vue components, Pinia stores, UI-library imports, authentication,
network clients, or product-specific API calls here. Keep those concerns in
the consuming application and expose only portable types, calculations,
parsers, and transformations from this package.
