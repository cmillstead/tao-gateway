from gateway.models import DebugLog


def test_debug_log_table_name() -> None:
    assert DebugLog.__tablename__ == "debug_logs"


def test_debug_log_columns() -> None:
    columns = {c.name for c in DebugLog.__table__.columns}
    expected = {
        "id", "usage_record_id", "api_key_id",
        "request_body", "response_body", "created_at",
    }
    assert columns == expected


def test_debug_log_indexes() -> None:
    index_names = {idx.name for idx in DebugLog.__table__.indexes}
    assert "ix_debug_logs_api_key_id_created_at" in index_names
    assert "ix_debug_logs_created_at" in index_names


def test_debug_log_foreign_keys() -> None:
    fks = {fk.target_fullname for fk in DebugLog.__table__.foreign_keys}
    assert "usage_records.id" in fks
    assert "api_keys.id" in fks
