from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RegistryVersionView(BaseModel):
    model_config = ConfigDict(extra="allow")

    manifest_path: str
    distribution_manifest_path: str
    bundle_path: str
    bundle_sha256: str | None = None
    attestation_path: str
    attestation_signature_path: str | None = None
    published_at: str
    stability: str
    installable: bool
    attestation_formats: list[str] = Field(default_factory=list)
    trust_state: str
    resolution: dict[str, Any]


class RegistrySkillView(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    kind: str
    display_name: str
    publisher: str | None = None
    qualified_name: str
    summary: str
    tags: list[str] = Field(default_factory=list)
    maturity: str
    quality_score: int | None = None
    capabilities: list[str] = Field(default_factory=list)
    last_verified_at: str | None = None
    use_when: list[str] = Field(default_factory=list)
    avoid_when: list[str] = Field(default_factory=list)
    runtime_assumptions: list[str] = Field(default_factory=list)
    runtime: dict[str, Any]
    agent_compatible: list[str] = Field(default_factory=list)
    compatibility: dict[str, Any]
    verified_support: dict[str, Any]
    trust_state: str
    default_install_version: str
    latest_version: str
    available_versions: list[str] = Field(default_factory=list)
    entrypoints: dict[str, Any]
    requires: dict[str, Any]
    interop: dict[str, Any]
    versions: dict[str, RegistryVersionView]


class RegistryAIIndexView(BaseModel):
    schema_version: int
    generated_at: str
    registry: dict[str, Any]
    install_policy: dict[str, Any]
    skills: list[RegistrySkillView] = Field(default_factory=list)


class RegistryDistributionEntryView(BaseModel):
    model_config = ConfigDict(extra="allow")

    kind: str
    name: str
    publisher: str
    qualified_name: str
    identity_mode: str
    version: str
    status: str
    summary: str
    manifest_path: str
    bundle_path: str
    bundle_sha256: str | None = None
    attestation_path: str
    attestation_signature_path: str
    published_at: str
    source_type: str
    display_name: str
    audience_type: str
    listing_mode: str
    release_id: int
    exposure_id: int
    metadata: dict[str, Any]
    compatibility: dict[str, Any]


class RegistryDistributionsView(BaseModel):
    schema_version: int
    generated_at: str
    skills: list[RegistryDistributionEntryView] = Field(default_factory=list)


class RegistryDiscoverySkillView(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    kind: str
    display_name: str | None = None
    qualified_name: str
    publisher: str | None = None
    summary: str
    source_registry: str
    source_priority: int
    match_names: list[str] = Field(default_factory=list)
    default_install_version: str
    latest_version: str
    available_versions: list[str] = Field(default_factory=list)
    runtime: dict[str, Any]
    runtime_readiness: str
    workspace_targets: list[str] = Field(default_factory=list)
    agent_compatible: list[str] = Field(default_factory=list)
    install_requires_confirmation: bool
    trust_level: str
    trust_state: str
    tags: list[str] = Field(default_factory=list)
    maturity: str
    quality_score: int
    last_verified_at: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    verified_support: dict[str, Any]
    attestation_formats: list[str] = Field(default_factory=list)
    use_when: list[str] = Field(default_factory=list)
    avoid_when: list[str] = Field(default_factory=list)
    runtime_assumptions: list[str] = Field(default_factory=list)


class RegistryDiscoveryView(BaseModel):
    schema_version: int
    generated_at: str
    default_registry: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    resolution_policy: dict[str, Any]
    skills: list[RegistryDiscoverySkillView] = Field(default_factory=list)


class RegistryCompatibilityEntryView(BaseModel):
    qualified_name: str
    name: str
    publisher: str
    version: str
    bundle_sha256: str | None = None


class RegistryCompatibilityView(BaseModel):
    schema_version: int
    generated_at: str
    skills: list[RegistryCompatibilityEntryView] = Field(default_factory=list)
