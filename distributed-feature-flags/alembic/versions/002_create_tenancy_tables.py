"""create_tenancy_tables

Revision ID: 002_create_tenancy_tables
Revises: 001_create_auth_tables
Create Date: 2026-06-05 01:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "002_create_tenancy_tables"
down_revision = "001_create_auth_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create organizations table
    op.create_table(
        "organizations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
    )

    # Create user_organizations table
    op.create_table(
        "user_organizations",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_user_organizations_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_organizations_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "organization_id", name=op.f("pk_user_organizations")),
    )

    # Create projects table
    op.create_table(
        "projects",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_projects_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )
    # Conditional unique index for active project names within the organization
    op.create_index(
        "idx_project_name_org_active",
        "projects",
        ["organization_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # Create environments table
    op.create_table(
        "environments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_environments_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_environments")),
    )
    # Conditional unique index for active environment names within the project
    op.create_index(
        "idx_env_name_project_active",
        "environments",
        ["project_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_env_name_project_active", table_name="environments")
    op.drop_table("environments")
    op.drop_index("idx_project_name_org_active", table_name="projects")
    op.drop_table("projects")
    op.drop_table("user_organizations")
    op.drop_table("organizations")
