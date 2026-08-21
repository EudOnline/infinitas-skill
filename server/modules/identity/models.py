from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from server.model_base import Base, utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(32), default="contributor")
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class Principal(Base):
    __tablename__ = "principals"
    __table_args__ = (
        UniqueConstraint("kind", "slug", name="uq_principals_kind_slug"),
        Index("ix_principals_kind_slug", "kind", "slug"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32))
    slug: Mapped[str] = mapped_column(String(200))
    display_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (Index("ix_teams_slug", "slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    principal_id: Mapped[int] = mapped_column(ForeignKey("principals.id"), unique=True)
    slug: Mapped[str] = mapped_column(String(200))
    display_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TeamMembership(Base):
    __tablename__ = "team_memberships"
    __table_args__ = (Index("ix_team_memberships_user_id_team_id", "user_id", "team_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("principals.id"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    role: Mapped[str] = mapped_column(String(64), default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ServicePrincipal(Base):
    __tablename__ = "service_principals"
    __table_args__ = (Index("ix_service_principals_slug", "slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    principal_id: Mapped[int] = mapped_column(ForeignKey("principals.id"), unique=True)
    slug: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    enrollment_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    state: Mapped[str] = mapped_column(String(32), default="active", index=True)
    policy_json: Mapped[str] = mapped_column(Text, default="{}")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AgentNamespaceReservation(Base):
    __tablename__ = "agent_namespace_reservations"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_agent_namespace_reservations_slug"),
        Index("ix_agent_namespace_reservations_state", "state"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(200))
    display_name: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(32), default="reserved")
    created_by_principal_id: Mapped[int] = mapped_column(ForeignKey("principals.id"))
    claimed_service_principal_id: Mapped[int | None] = mapped_column(
        ForeignKey("service_principals.id"), nullable=True
    )
    released_by_principal_id: Mapped[int | None] = mapped_column(
        ForeignKey("principals.id"), nullable=True
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AgentInvitation(Base):
    __tablename__ = "agent_invitations"
    __table_args__ = (
        UniqueConstraint("public_id", name="uq_agent_invitations_public_id"),
        UniqueConstraint("request_nonce_hash", name="uq_agent_invitations_request_nonce_hash"),
        Index("ix_agent_invitations_reservation_state", "reservation_id", "state"),
        Index(
            "uq_agent_invitations_open_reservation",
            "reservation_id",
            unique=True,
            sqlite_where=text("state = 'open'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(64))
    reservation_id: Mapped[int] = mapped_column(ForeignKey("agent_namespace_reservations.id"))
    purpose: Mapped[str] = mapped_column(String(32), default="enroll")
    target_service_principal_id: Mapped[int | None] = mapped_column(
        ForeignKey("service_principals.id"), nullable=True
    )
    invitation_hash: Mapped[str] = mapped_column(String(255))
    request_nonce_hash: Mapped[str] = mapped_column(String(255))
    policy_json: Mapped[str] = mapped_column(Text, default="{}")
    state: Mapped[str] = mapped_column(String(32), default="open")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_principal_id: Mapped[int] = mapped_column(ForeignKey("principals.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AgentEnrollment(Base):
    __tablename__ = "agent_enrollments"
    __table_args__ = (
        UniqueConstraint("public_id", name="uq_agent_enrollments_public_id"),
        UniqueConstraint("invitation_id", name="uq_agent_enrollments_invitation_id"),
        Index("ix_agent_enrollments_state", "state"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(64))
    invitation_id: Mapped[int] = mapped_column(ForeignKey("agent_invitations.id"))
    status_hash: Mapped[str] = mapped_column(String(255))
    proposed_api_key_hash: Mapped[str] = mapped_column(String(255))
    fingerprint: Mapped[str] = mapped_column(String(32))
    runtime_metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    state: Mapped[str] = mapped_column(String(32), default="pending")
    decision_note: Mapped[str] = mapped_column(Text, default="")
    decision_by_principal_id: Mapped[int | None] = mapped_column(
        ForeignKey("principals.id"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Credential(Base):
    __tablename__ = "credentials"
    __table_args__ = (
        Index(
            "ix_credentials_principal_id_type_revoked_at_expires_at",
            "principal_id",
            "type",
            "revoked_at",
            "expires_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    principal_id: Mapped[int | None] = mapped_column(ForeignKey("principals.id"), nullable=True)
    grant_id: Mapped[int | None] = mapped_column(ForeignKey("access_grants.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(64))
    product_token_name: Mapped[str] = mapped_column(String(200), default="")
    product_token_type: Mapped[str] = mapped_column(String(32), default="")
    product_object_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    product_scope_type: Mapped[str] = mapped_column(String(32), default="")
    product_scope_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    issued_for: Mapped[str] = mapped_column(String(200), default="")
    hashed_secret: Mapped[str] = mapped_column(String(255))
    scopes_json: Mapped[str] = mapped_column(Text, default="[]")
    resource_selector_json: Mapped[str] = mapped_column(Text, default="{}")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
