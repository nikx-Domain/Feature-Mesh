import pytest
import uuid
from unittest.mock import AsyncMock
from app.application.use_cases.get_environment_snapshot import GetEnvironmentSnapshotUseCase
from app.domain.exceptions import EntityNotFoundException
from app.domain.entities import FeatureFlagEntity, FeatureFlagEnvironmentEntity, FlagVariationEntity, TargetingRuleEntity, RolloutRuleEntity, FlagType, TargetingOperator
from app.infrastructure.db.models import Environment

@pytest.fixture
def mock_uow():
    uow = AsyncMock()
    # Support async with
    uow.__aenter__.return_value = uow
    uow.__aexit__.return_value = False
    return uow

@pytest.fixture
def use_case(mock_uow):
    return GetEnvironmentSnapshotUseCase(mock_uow)

@pytest.mark.asyncio
async def test_execute_environment_not_found(use_case, mock_uow):
    mock_uow.environments.get_by_id.return_value = None
    with pytest.raises(EntityNotFoundException):
        await use_case.execute(uuid.uuid4())

@pytest.mark.asyncio
async def test_execute_success(use_case, mock_uow):
    env_id = uuid.uuid4()
    proj_id = uuid.uuid4()
    flag_id = uuid.uuid4()
    ff_env_id = uuid.uuid4()
    var_id = uuid.uuid4()
    
    mock_uow.environments.get_by_id.return_value = Environment(id=env_id, project_id=proj_id, name="Test")
    
    mock_uow.feature_flags.list_for_project.return_value = [
        FeatureFlagEntity(id=flag_id, project_id=proj_id, name="Flag 1", key="flag1", type=FlagType.BOOLEAN, version=1)
    ]
    
    mock_uow.feature_flag_environments.list_for_environment.return_value = [
        FeatureFlagEnvironmentEntity(id=ff_env_id, feature_flag_id=flag_id, environment_id=env_id, is_enabled=True, default_serve_variation_id=var_id, off_variation_id=var_id)
    ]
    
    mock_uow.flag_variations.list_for_flag.return_value = [
        FlagVariationEntity(id=var_id, feature_flag_id=flag_id, name="var1", value=True)
    ]
    
    mock_uow.targeting_rules.list_for_state.return_value = [
        TargetingRuleEntity(id=uuid.uuid4(), feature_flag_environment_id=ff_env_id, attribute="test", operator=TargetingOperator.EQUALS, value="1", serve_variation_id=var_id, priority=0)
    ]
    
    mock_uow.rollout_rules.list_for_state.return_value = [
        RolloutRuleEntity(id=uuid.uuid4(), feature_flag_environment_id=ff_env_id, percentage=100, serve_variation_id=var_id)
    ]
    
    result = await use_case.execute(env_id)
    assert result["environment_id"] == str(env_id)
    assert "flag1" in result["flags"]
    flag_data = result["flags"]["flag1"]
    assert flag_data["id"] == str(flag_id)
    assert flag_data["environment"]["is_enabled"] is True
    assert len(flag_data["environment"]["targeting_rules"]) == 1
    assert len(flag_data["environment"]["rollout_rules"]) == 1
    assert len(flag_data["variations"]) == 1
