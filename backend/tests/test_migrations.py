import os
import pytest
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect


def test_alembic_migration_lifecycle(tmp_path):
    """Test full Alembic migration upgrade, downgrade, and re-upgrade lifecycle."""
    test_db_path = tmp_path / "test_migration.db"
    test_db_url = f"sqlite:///{test_db_path}"

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", test_db_url)
    cfg.set_main_option("script_location", "migrations")

    # 1. Upgrade to head
    command.upgrade(cfg, "head")

    engine = create_engine(test_db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    expected_tables = {
        "users",
        "roles",
        "permissions",
        "role_permissions",
        "user_roles",
        "tenders",
        "tender_documents",
        "tender_requirements",
        "bids",
        "bid_documents",
        "document_extractions",
        "extracted_entities",
        "evidence",
        "compliance_rules",
        "compliance_results",
        "verification_records",
        "review_tasks",
        "review_decisions",
        "reports",
        "notifications",
        "audit_logs",
    }

    assert expected_tables.issubset(set(tables)), f"Missing tables: {expected_tables - set(tables)}"

    # 2. Downgrade to base
    command.downgrade(cfg, "base")
    inspector = inspect(engine)
    remaining_tables = [t for t in inspector.get_table_names() if t != "alembic_version"]
    assert len(remaining_tables) == 0, f"Tables remained after downgrade: {remaining_tables}"

    # 3. Re-upgrade to head
    command.upgrade(cfg, "head")
    inspector = inspect(engine)
    recreated_tables = inspector.get_table_names()
    assert expected_tables.issubset(set(recreated_tables))

    engine.dispose()
