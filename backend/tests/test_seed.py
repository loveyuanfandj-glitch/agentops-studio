from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from agentops.database import Base
from agentops.models import AgentRun, CommerceOrder, RevenueSummaryRecord, Tenant
from agentops.seed import seed_demo_data


# Validates a fresh database receives dashboard and operational records exactly once,
# covering the production startup seed path and its idempotent repeat invocation.
async def test_seed_demo_data_is_complete_and_idempotent(tmp_path: Path) -> None:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'seed-test.db'}"
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        await seed_demo_data(session)
        await seed_demo_data(session)

        tenant_count = await session.scalar(
            select(func.count()).select_from(Tenant)
        )
        run_count = await session.scalar(
            select(func.count()).select_from(AgentRun)
        )
        revenue_count = await session.scalar(
            select(func.count()).select_from(RevenueSummaryRecord)
        )
        order_count = await session.scalar(
            select(func.count()).select_from(CommerceOrder)
        )

    await engine.dispose()

    assert tenant_count == 3
    assert run_count == 7
    assert revenue_count == 1
    assert order_count == 3
