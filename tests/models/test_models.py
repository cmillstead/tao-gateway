from gateway.models import ApiKey, Base, Organization


def test_organization_table_name() -> None:
    assert Organization.__tablename__ == "organizations"


def test_api_key_table_name() -> None:
    assert ApiKey.__tablename__ == "api_keys"


def test_base_metadata_has_tables() -> None:
    table_names = set(Base.metadata.tables.keys())
    assert "organizations" in table_names
    assert "api_keys" in table_names


def test_organization_columns() -> None:
    columns = {c.name for c in Organization.__table__.columns}
    assert columns == {"id", "email", "password_hash", "created_at", "updated_at"}


def test_api_key_columns() -> None:
    columns = {c.name for c in ApiKey.__table__.columns}
    expected = {
        "id", "org_id", "name", "prefix", "key_hash",
        "is_active", "debug_mode", "created_at", "updated_at",
    }
    assert columns == expected


def test_organization_has_id_default() -> None:
    col = Organization.__table__.columns["id"]
    assert col.default is not None, "Organization.id should have a Python-side default"


def test_api_key_foreign_key() -> None:
    fks = [fk.target_fullname for fk in ApiKey.__table__.foreign_keys]
    assert "organizations.id" in fks


def test_api_key_prefix_is_unique() -> None:
    prefix_col = ApiKey.__table__.columns["prefix"]
    assert prefix_col.unique is True


def test_organization_email_is_unique() -> None:
    email_col = Organization.__table__.columns["email"]
    assert email_col.unique is True
