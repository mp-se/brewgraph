# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Model registration bootstrap.

Importing this package runs every bundled `oss.models.*` module's module-level
`register_model()` call, populating `core.models.registry` so `resolve_model()`
can find each class. This is the single place the module list lives — a
caller that needs models registered before it runs further imports (as
`main_oss.py` and `migrations/env.py` both do, since core services resolve
models at their own import time) does `import oss.models as _oss_models  # noqa: F401`.
That has to be an import statement rather than a `register_models()` call:
a plain function call between two import statements makes every import
after it "not at the top of the module" (pylint C0413), which a bare
`import` does not. Previously this exact module list was duplicated
verbatim in `main_oss.py` and `migrations/env.py`; both now import this
package instead.

`oss.models.platform` (`TenantSettings`) is deliberately excluded from this
bundle so it stays independently importable. `register_model()` maps a class
onto a shared SQLAlchemy `Base.metadata`; a second class mapped to the same
table name on that same metadata raises at import time, so any module that
needs to substitute its own `TenantSettings` mapped to the `tenant_settings`
table must be able to import the other 12 models here without also forcing
this one to load. The other 12 modules have no such collision risk and are
safe to bundle unconditionally. Code that wants this package's own
`TenantSettings` registered (this app's own entrypoint and its own migration
entrypoint) imports `oss.models.platform` explicitly, alongside this package.
"""
import oss.models.batch as _batch  # noqa: F401
import oss.models.batch_dry_hop as _batch_dry_hop  # noqa: F401
import oss.models.batch_note as _batch_note  # noqa: F401
import oss.models.device as _device  # noqa: F401
import oss.models.fermentation_step as _fermentation_step  # noqa: F401
import oss.models.gravity_reading as _gravity_reading  # noqa: F401
import oss.models.integration as _integration  # noqa: F401
import oss.models.pour_event as _pour_event  # noqa: F401
import oss.models.prediction as _prediction  # noqa: F401
import oss.models.pressure_reading as _pressure_reading  # noqa: F401
import oss.models.temp_reading as _temp_reading  # noqa: F401
import oss.models.storage_vessel as _storage_vessel  # noqa: F401
import oss.models.tap as _tap  # noqa: F401
