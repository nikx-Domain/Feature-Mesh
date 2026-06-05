import uuid

from app.domain.unit_of_work import UnitOfWork
from app.infrastructure.db.models import Organization, OrgRole, User, UserOrganization


class CreateOrganizationUseCase:
    """Use case to handle creating organizations and establishing the caller as owner."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def execute(self, name: str, user: User) -> Organization:
        async with self.uow:
            # Create organization
            org_id = uuid.uuid4()
            org = Organization(id=org_id, name=name)
            await self.uow.organizations.add(org)

            # Create default membership as OWNER
            membership = UserOrganization(
                user_id=user.id,
                organization_id=org.id,
                role=OrgRole.OWNER,
            )
            await self.uow.organizations.add_membership(membership)

            await self.uow.commit()
            return org
