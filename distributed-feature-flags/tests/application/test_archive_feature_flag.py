import pytest
import uuid
from unittest.mock import AsyncMock
from app.application.use_cases.archive_feature_flag import ArchiveFeatureFlagUseCase
from app.domain.exceptions import EntityNotFoundException
from app.domain.entities import FeatureFlagEntity

@pytest.fixture
def mock_uow():
    uow = AsyncMock()
    uow.__aenter__.return_value = uow
    uow.__aexit__.return_value = False
    return uow

@pytest.fixture
def use_case(mock_uow):
    return ArchiveFeatureFlagUseCase(mock_uow)

@pytest.mark.asyncio
async def test_execute_flag_not_found(use_case, mock_uow):
    mock_uow.feature_flags.get_by_id.return_value = None
    with pytest.raises(EntityNotFoundException):
        await use_case.execute(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

@pytest.mark.asyncio
async def test_execute_flag_already_archived(use_case, mock_uow):
    flag_id = uuid.uuid4()
    flag = FeatureFlagEntity(id=flag_id, project_id=uuid.uuid4(), name="Flag", key="flag", version=1, is_archived=True)
    mock_uow.feature_flags.get_by_id.return_value = flag
    
    result = await use_case.execute(flag_id, uuid.uuid4(), uuid.uuid4())
    
    assert result.is_archived is True
    assert result.version == 1
    mock_uow.feature_flags.update.assert_not_called()
    mock_uow.outbox_events.add.assert_not_called()
    mock_uow.commit.assert_called_once()

@pytest.mark.asyncio
async def test_execute_success(use_case, mock_uow):
    flag_id = uuid.uuid4()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    
    flag = FeatureFlagEntity(id=flag_id, project_id=uuid.uuid4(), name="Flag", key="flag", version=1, is_archived=False)
    mock_uow.feature_flags.get_by_id.return_value = flag
    
    result = await use_case.execute(flag_id, org_id, user_id)
    
    assert result.is_archived is True
    assert result.version == 2
    mock_uow.feature_flags.update.assert_called_once_with(flag)
    mock_uow.outbox_events.add.assert_called_once()
    mock_uow.commit.assert_called_once()
