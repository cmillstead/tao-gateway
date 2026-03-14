import pytest
from pydantic import ValidationError

from gateway.schemas.code import CodeChoice, CodeCompletionRequest, CodeCompletionResponse


class TestCodeCompletionRequest:
    def test_valid_minimal(self):
        req = CodeCompletionRequest(prompt="Write hello world", language="python")
        assert req.model == "tao-sn62"
        assert req.prompt == "Write hello world"
        assert req.language == "python"
        assert req.context is None

    def test_valid_all_fields(self):
        req = CodeCompletionRequest(
            model="tao-sn62",
            prompt="Add error handling",
            language="typescript",
            context="function foo() { return 1; }",
        )
        assert req.model == "tao-sn62"
        assert req.language == "typescript"
        assert req.context == "function foo() { return 1; }"

    def test_prompt_required(self):
        with pytest.raises(ValidationError):
            CodeCompletionRequest(language="python")

    def test_language_required(self):
        with pytest.raises(ValidationError):
            CodeCompletionRequest(prompt="Write code")

    def test_prompt_empty_rejected(self):
        with pytest.raises(ValidationError):
            CodeCompletionRequest(prompt="", language="python")

    def test_language_empty_rejected(self):
        with pytest.raises(ValidationError):
            CodeCompletionRequest(prompt="Write code", language="")

    def test_prompt_max_length(self):
        with pytest.raises(ValidationError):
            CodeCompletionRequest(prompt="x" * 16001, language="python")

    def test_prompt_at_max_length(self):
        req = CodeCompletionRequest(prompt="x" * 16000, language="python")
        assert len(req.prompt) == 16000

    def test_language_max_length(self):
        with pytest.raises(ValidationError):
            CodeCompletionRequest(prompt="test", language="x" * 33)

    def test_context_max_length(self):
        with pytest.raises(ValidationError):
            CodeCompletionRequest(
                prompt="test", language="python", context="x" * 32001
            )

    def test_context_at_max_length(self):
        req = CodeCompletionRequest(
            prompt="test", language="python", context="x" * 32000
        )
        assert len(req.context) == 32000

    def test_context_none_allowed(self):
        req = CodeCompletionRequest(prompt="test", language="python", context=None)
        assert req.context is None

    def test_model_empty_rejected(self):
        with pytest.raises(ValidationError):
            CodeCompletionRequest(prompt="test", language="python", model="")

    def test_model_max_length(self):
        with pytest.raises(ValidationError):
            CodeCompletionRequest(prompt="test", language="python", model="x" * 65)


class TestCodeChoice:
    def test_valid(self):
        choice = CodeChoice(index=0, code="x = 1", language="python")
        assert choice.index == 0
        assert choice.code == "x = 1"
        assert choice.language == "python"
        assert choice.finish_reason == "stop"

    def test_finish_reason_default(self):
        choice = CodeChoice(index=0, code="x", language="py")
        assert choice.finish_reason == "stop"


class TestCodeCompletionResponse:
    def test_valid_response(self):
        resp = CodeCompletionResponse(
            id="codecmpl-test123",
            created=1234567890,
            model="tao-sn62",
            choices=[CodeChoice(index=0, code="x = 1", language="python")],
        )
        assert resp.id == "codecmpl-test123"
        assert resp.object == "code.completion"
        assert resp.created == 1234567890
        assert resp.model == "tao-sn62"
        assert len(resp.choices) == 1

    def test_empty_choices(self):
        resp = CodeCompletionResponse(
            id="codecmpl-test",
            created=123,
            model="tao-sn62",
            choices=[],
        )
        assert resp.choices == []

    def test_multiple_choices(self):
        resp = CodeCompletionResponse(
            id="codecmpl-test",
            created=123,
            model="tao-sn62",
            choices=[
                CodeChoice(index=0, code="x = 1", language="python"),
                CodeChoice(index=1, code="let x = 1;", language="javascript"),
            ],
        )
        assert len(resp.choices) == 2
