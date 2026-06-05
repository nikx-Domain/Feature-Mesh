import uuid
from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Table,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class OrgRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


# Association table for User and Role (Many-to-Many)
UserRole = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Uuid(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

# Association table for Role and Permission (Many-to-Many)
RolePermission = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Uuid(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Uuid(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class UserOrganization(Base):
    __tablename__ = "user_organizations"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[OrgRole] = mapped_column(String(50), default=OrgRole.MEMBER, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="memberships")
    organization: Mapped["Organization"] = relationship("Organization", back_populates="memberships")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False
    )

    # Relationships
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary=UserRole,
        back_populates="users",
        lazy="selectin"
    )
    memberships: Mapped[list["UserOrganization"]] = relationship(
        "UserOrganization",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    # Relationships
    users: Mapped[list["User"]] = relationship(
        "User",
        secondary=UserRole,
        back_populates="roles"
    )
    permissions: Mapped[list["Permission"]] = relationship(
        "Permission",
        secondary=RolePermission,
        back_populates="roles",
        lazy="selectin"
    )


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=True)

    # Relationships
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary=RolePermission,
        back_populates="permissions"
    )


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    memberships: Mapped[list["UserOrganization"]] = relationship(
        "UserOrganization",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    projects: Mapped[list["Project"]] = relationship(
        "Project",
        back_populates="organization",
        cascade="all, delete-orphan"
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="projects")
    environments: Mapped[list["Environment"]] = relationship(
        "Environment",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    __table_args__ = (
        Index("idx_project_name_org_active", "organization_id", "name", unique=True, postgresql_where=text("deleted_at IS NULL"), sqlite_where=text("deleted_at IS NULL")),
    )


class Environment(Base):
    __tablename__ = "environments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="environments")

    __table_args__ = (
        Index("idx_env_name_project_active", "project_id", "name", unique=True, postgresql_where=text("deleted_at IS NULL"), sqlite_where=text("deleted_at IS NULL")),
    )
