import uuid
from typing import Any
from app.domain.unit_of_work import UnitOfWork
from app.infrastructure.db.models import Organization, UserOrganization, OrgRole, User
from app.infrastructure.repositories.base import SQLAlchemyRepository


class CreateOrganizationUseCase:
    """Use case to handle creating organizations and establishing the caller as owner."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(self, name: str, user: User) -> Organization:
        async with self.uow:
            # Create organization
            org = Organization(name=name)
            org_repo: SQLAlchemyRepository[Organization, uuid.UUID] = SQLAlchemyRepository(
                self.uow.session, Organization
            )
            await org_repo.add(org)

            # Flush to database to generate the UUID
            await self.uow.session.flush()

            # Create default membership as OWNER
            membership = UserOrganization(
                user_id=user.id,
                organization_id=org.id,
                role=OrgRole.OWNER,
            )
            membership_repo: SQLAlchemyRepository[UserOrganization, Any] = SQLAlchemyRepository(
                self.uow.session, UserOrganization
            )
            await membership_repo.add(membership)

            await self.uow.commit()
            return org
