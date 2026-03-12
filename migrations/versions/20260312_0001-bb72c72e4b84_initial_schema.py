"""initial schema

Revision ID: bb72c72e4b84
Revises:
Create Date: 2026-03-12 00:01:00.000000

Creates the core Ghost Backend tables: users, roles, permissions,
user_roles, role_permissions, and user_sessions.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "bb72c72e4b84"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- roles ---
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        # TimestampMixin
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # AuditMixin
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("audit_log", sa.JSON, nullable=False, server_default="[]"),
    )
    op.create_index("ix_roles_name", "roles", ["name"], unique=True)

    # --- permissions ---
    op.create_table(
        "permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("resource", sa.String(100), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_permissions_name", "permissions", ["name"], unique=True)
    op.create_index("ix_permissions_resource", "permissions", ["resource"])
    op.create_index(
        "ix_permissions_resource_action",
        "permissions",
        ["resource", "action"],
        unique=True,
    )

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(100), unique=True, nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        # Profile
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("bio", sa.Text, nullable=True),
        # Status
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_superuser", sa.Boolean, nullable=False, server_default="false"),
        # Auth
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("login_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed_login_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        # 2FA
        sa.Column("two_factor_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("two_factor_secret", sa.String(255), nullable=True),
        # JSON
        sa.Column("settings", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("user_metadata", sa.JSON, nullable=False, server_default="{}"),
        # TimestampMixin
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # SoftDeleteMixin
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        # AuditMixin
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("audit_log", sa.JSON, nullable=False, server_default="[]"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_is_deleted", "users", ["is_deleted"])
    op.create_index("ix_users_email_active", "users", ["email", "is_active"])
    op.create_index("ix_users_username_active", "users", ["username", "is_active"])

    # --- user_roles (M2M) ---
    op.create_table(
        "user_roles",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),
    )

    # --- role_permissions (M2M) ---
    op.create_table(
        "role_permissions",
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "permission_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("permissions.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )

    # --- user_sessions ---
    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token", sa.String(500), unique=True, nullable=False),
        sa.Column("refresh_token", sa.String(500), unique=True, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("device_id", sa.String(255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_user_sessions_token", "user_sessions", ["token"], unique=True)
    op.create_index(
        "ix_user_sessions_refresh_token",
        "user_sessions",
        ["refresh_token"],
        unique=True,
    )

    # --- Seed default roles ---
    op.execute(
        """
        INSERT INTO roles (id, name, description, is_system, priority, created_at, updated_at, version, audit_log)
        VALUES
            (gen_random_uuid(), 'admin',  'Full system access',          true, 100, NOW(), NOW(), 1, '[]'),
            (gen_random_uuid(), 'user',   'Standard authenticated user', true,  50, NOW(), NOW(), 1, '[]'),
            (gen_random_uuid(), 'guest',  'Read-only guest access',      true,  10, NOW(), NOW(), 1, '[]'),
            (gen_random_uuid(), 'api',    'API-key service account',     true,  30, NOW(), NOW(), 1, '[]')
        ON CONFLICT (name) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.drop_table("user_sessions")
    op.drop_table("role_permissions")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("permissions")
    op.drop_table("roles")
