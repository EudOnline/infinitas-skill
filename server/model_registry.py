"""Import ORM model owners so Alembic can populate ``Base.metadata``."""

import server.modules.access.models as _access_models  # noqa: F401
import server.modules.audit.models as _audit_models  # noqa: F401
import server.modules.authoring.models as _authoring_models  # noqa: F401
import server.modules.exposure.models as _exposure_models  # noqa: F401
import server.modules.identity.models as _identity_models  # noqa: F401
import server.modules.jobs.models as _jobs_models  # noqa: F401
import server.modules.release.models as _release_models  # noqa: F401
import server.modules.review.models as _review_models  # noqa: F401
from server import rate_limit as _rate_limit  # noqa: F401

__all__: tuple[str, ...] = ()
