import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.use_cases.evaluate_feature_flag import EvaluateFeatureFlagUseCase
from app.domain.cache.models import EvaluationDataCacheDTO
from app.domain.entities import (
    FeatureFlagEntity,
    FeatureFlagEnvironmentEntity,
)
from app.domain.evaluation.models import EvaluationContext, EvaluationReason


@pytest.fixture
def mock_cache_service():
    service = AsyncMock()
    service.get.return_value = None
    service.set.return_value = None
    return service


@pytest.fixture
def mock_uow():
    uow = AsyncMock()
    uow.__aenter__.return_value = uow
    uow.__aexit__.return_value = None

    env = MagicMock()
    env.project_id = uuid.uuid4()
    env.deleted_at = None
    uow.environments.get_by_id.return_value = env

    flag = FeatureFlagEntity(project_id=env.project_id, name="Test", key="test-flag")
    uow.feature_flags.get_by_key_and_project.return_value = flag

    state = FeatureFlagEnvironmentEntity(
        feature_flag_id=flag.id,
        environment_id=uuid.uuid4(),
        is_enabled=True,
    )
    uow.feature_flag_environments.get_by_flag_and_environment.return_value = state

    uow.flag_variations.list_for_flag.return_value = []

    # Store references for testing
    uow._flag = flag
    uow._state = state
    return uow


@pytest.mark.anyio
async def test_cache_miss_queries_db_and_populates_cache(mock_uow, mock_cache_service):
    use_case = EvaluateFeatureFlagUseCase(mock_uow, mock_cache_service)

    env_id = mock_uow._state.environment_id
    flag_key = "test-flag"
    context = EvaluationContext(key="user1")

    decision = await use_case.execute(env_id, flag_key, context)

    # Assert cache was checked
    mock_cache_service.get.assert_any_call(f"eval_ptr:{env_id}:{flag_key}")

    # Assert DB was queried
    mock_uow.environments.get_by_id.assert_called_once()
    mock_uow.feature_flags.get_by_key_and_project.assert_called_once()

    # Assert Cache was populated
    assert mock_cache_service.set.call_count == 2
    mock_cache_service.set.assert_any_call(
        f"eval_data:{env_id}:{flag_key}:v1",
        mock_cache_service.set.call_args_list[0][0][1], # check value matches dump
        expire_seconds=3600
    )
    mock_cache_service.set.assert_any_call(
        f"eval_ptr:{env_id}:{flag_key}",
        "1",
        expire_seconds=3600
    )

    assert decision.metadata["cache_hit"] is False
    assert decision.reason == EvaluationReason.DEFAULT


@pytest.mark.anyio
async def test_cache_hit_skips_db(mock_uow, mock_cache_service):
    env_id = mock_uow._state.environment_id
    flag_key = "test-flag"

    # Mock cache hit
    mock_cache_service.get.side_effect = lambda key: "1" if "eval_ptr" in key else dto_json

    dto = EvaluationDataCacheDTO(
        flag=mock_uow._flag,
        environment=mock_uow._state,
        variations=[]
    )
    dto_json = dto.model_dump_json()

    use_case = EvaluateFeatureFlagUseCase(mock_uow, mock_cache_service)
    context = EvaluationContext(key="user2")

    decision = await use_case.execute(env_id, flag_key, context)

    # Assert DB was NEVER queried
    mock_uow.environments.get_by_id.assert_not_called()
    mock_uow.feature_flags.get_by_key_and_project.assert_not_called()

    assert decision.metadata["cache_hit"] is True
    assert decision.reason == EvaluationReason.DEFAULT
