from __future__ import annotations

from sqlalchemy.orm import Session

from server.models import AccessCredential, AccessGrant, Exposure, Release, ReviewCase
from server.modules.shared.enums import ExposureMode, ReviewRequirement


def create_release_exposure(
    db: Session,
    release: Release,
    *,
    mode: str,
    credential_token: str | None = None,
) -> tuple[Exposure, ReviewCase | None, AccessGrant | None, AccessCredential | None]:
    if mode not in {item.value for item in ExposureMode}:
        raise ValueError(f'unsupported exposure mode {mode!r}')

    review_requirement = (
        ReviewRequirement.BLOCKING.value if mode == ExposureMode.PUBLIC.value else ReviewRequirement.NONE.value
    )
    exposure = Exposure(
        release_id=release.id,
        mode=mode,
        review_requirement=review_requirement,
    )
    db.add(exposure)
    db.flush()

    review_case = None
    grant = None
    credential = None
    if mode == ExposureMode.PUBLIC.value:
        review_case = ReviewCase(
            exposure_id=exposure.id,
            release_id=release.id,
            status='pending',
        )
        db.add(review_case)
    elif mode == ExposureMode.GRANT.value:
        grant = AccessGrant(
            exposure_id=exposure.id,
            release_id=release.id,
        )
        db.add(grant)
        db.flush()
        credential = AccessCredential(
            grant_id=grant.id,
            token=credential_token or f'grant-{release.id}',
        )
        db.add(credential)

    db.flush()
    return exposure, review_case, grant, credential
