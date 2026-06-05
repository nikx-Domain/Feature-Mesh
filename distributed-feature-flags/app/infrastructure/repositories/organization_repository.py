import uuid
from collections.abc import Sequence

from sqlalchemy.future import select

from app.domain.repositories.organization_repository import OrganizationRepository
from app.infrastructure.db.models import Organization, UserOrganization
from app.infrastructure.repositories.base import SQLAlchemyRepository


class SQLAlchemyOrganizationRepository(
    SQLAlchemyRepository[Organization, uuid.UUID], OrganizationRepository
):
    """SQLAlchemy implementation of the OrganizationRepository interface."""

    def __init__(self, session) -> None:
        super().__init__(session, Organization)

    async def list_for_user(self, user_id: uuid.UUID) -> Sequence[Organization]:
        stmt = (
            select(Organization)
            .join(UserOrganization)
            .where(UserOrganization.user_id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_membership(
        self, user_id: uuid.UUID, organization_id: uuid.UUID
    ) -> UserOrganization | None:
        stmt = select(UserOrganization).where(
            UserOrganization.user_id == user_id,
            UserOrganization.organization_id == organization_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def add_membership(self, membership: UserOrganization) -> None:
        self.session.add(membership)
