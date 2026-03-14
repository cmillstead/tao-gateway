import pytest
from pydantic import ValidationError

from gateway.schemas.models import ModelsListResponse, SubnetModelInfo


class TestSubnetModelInfo:
    def test_valid_minimal(self):
        info = SubnetModelInfo(
            id="tao-sn1",
            created=1710288000,
            subnet_id=1,
            capability="Text Generation",
            status="available",
        )
        assert info.id == "tao-sn1"
        assert info.object == "model"
        assert info.owned_by == "tao-gateway"
        assert info.subnet_id == 1
        assert info.capability == "Text Generation"
        assert info.status == "available"
        assert info.parameters == {}

    def test_valid_with_parameters(self):
        info = SubnetModelInfo(
            id="tao-sn1",
            created=1710288000,
            subnet_id=1,
            capability="Text Generation",
            status="available",
            parameters={"model": "string (required)", "stream": "boolean (optional)"},
        )
        assert info.parameters["model"] == "string (required)"

    def test_status_must_be_valid_literal(self):
        with pytest.raises(ValidationError):
            SubnetModelInfo(
                id="tao-sn1",
                created=1710288000,
                subnet_id=1,
                capability="Text Generation",
                status="broken",  # type: ignore[arg-type]
            )

    def test_unavailable_status(self):
        info = SubnetModelInfo(
            id="tao-sn62",
            created=1710288000,
            subnet_id=62,
            capability="Code Generation",
            status="unavailable",
        )
        assert info.status == "unavailable"

    def test_object_is_always_model(self):
        info = SubnetModelInfo(
            id="tao-sn1",
            created=1710288000,
            subnet_id=1,
            capability="Text Generation",
            status="available",
        )
        assert info.object == "model"


class TestModelsListResponse:
    def test_empty_list(self):
        resp = ModelsListResponse(data=[])
        assert resp.object == "list"
        assert resp.data == []

    def test_with_models(self):
        model = SubnetModelInfo(
            id="tao-sn1",
            created=1710288000,
            subnet_id=1,
            capability="Text Generation",
            status="available",
        )
        resp = ModelsListResponse(data=[model])
        assert len(resp.data) == 1
        assert resp.data[0].id == "tao-sn1"

    def test_multiple_models(self):
        models = [
            SubnetModelInfo(
                id=f"tao-sn{n}",
                created=1710288000,
                subnet_id=n,
                capability="Test",
                status="available",
            )
            for n in [1, 19, 62]
        ]
        resp = ModelsListResponse(data=models)
        assert len(resp.data) == 3

    def test_serialization_format(self):
        model = SubnetModelInfo(
            id="tao-sn1",
            created=1710288000,
            subnet_id=1,
            capability="Text Generation",
            status="available",
            parameters={"model": "string (required)"},
        )
        resp = ModelsListResponse(data=[model])
        d = resp.model_dump()
        assert d["object"] == "list"
        assert d["data"][0]["object"] == "model"
        assert d["data"][0]["owned_by"] == "tao-gateway"
