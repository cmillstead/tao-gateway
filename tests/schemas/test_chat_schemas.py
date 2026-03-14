import pytest
from pydantic import ValidationError


def test_chat_message_valid():
    from gateway.schemas.chat import ChatMessage

    msg = ChatMessage(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"


def test_chat_message_invalid_role():
    from gateway.schemas.chat import ChatMessage

    with pytest.raises(ValidationError):
        ChatMessage(role="invalid_role", content="Hello")


def test_chat_message_valid_roles():
    from gateway.schemas.chat import ChatMessage

    for role in ("system", "user", "assistant"):
        msg = ChatMessage(role=role, content="test")
        assert msg.role == role


def test_request_valid_minimal():
    from gateway.schemas.chat import ChatCompletionRequest

    req = ChatCompletionRequest(
        model="tao-sn1",
        messages=[{"role": "user", "content": "Hello"}],
    )
    assert req.model == "tao-sn1"
    assert len(req.messages) == 1
    assert req.stream is False


def test_request_valid_with_optional_fields():
    from gateway.schemas.chat import ChatCompletionRequest

    req = ChatCompletionRequest(
        model="tao-sn1",
        messages=[{"role": "user", "content": "Hello"}],
        temperature=0.7,
        max_tokens=100,
        top_p=0.9,
    )
    assert req.temperature == 0.7
    assert req.max_tokens == 100
    assert req.top_p == 0.9


def test_request_empty_messages_rejected():
    from gateway.schemas.chat import ChatCompletionRequest

    with pytest.raises(ValidationError, match="messages"):
        ChatCompletionRequest(model="tao-sn1", messages=[])


def test_request_no_user_message_rejected():
    from gateway.schemas.chat import ChatCompletionRequest

    with pytest.raises(ValidationError, match="user"):
        ChatCompletionRequest(
            model="tao-sn1",
            messages=[{"role": "system", "content": "You are helpful"}],
        )


def test_request_temperature_out_of_range():
    from gateway.schemas.chat import ChatCompletionRequest

    with pytest.raises(ValidationError, match="temperature"):
        ChatCompletionRequest(
            model="tao-sn1",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=2.5,
        )


def test_request_temperature_negative():
    from gateway.schemas.chat import ChatCompletionRequest

    with pytest.raises(ValidationError, match="temperature"):
        ChatCompletionRequest(
            model="tao-sn1",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=-0.1,
        )


def test_request_max_tokens_negative_rejected():
    from gateway.schemas.chat import ChatCompletionRequest

    with pytest.raises(ValidationError, match="max_tokens"):
        ChatCompletionRequest(
            model="tao-sn1",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=-1,
        )


def test_request_max_tokens_zero_rejected():
    from gateway.schemas.chat import ChatCompletionRequest

    with pytest.raises(ValidationError, match="max_tokens"):
        ChatCompletionRequest(
            model="tao-sn1",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=0,
        )


def test_request_max_tokens_exceeds_upper_bound_rejected():
    from gateway.schemas.chat import ChatCompletionRequest

    with pytest.raises(ValidationError, match="max_tokens"):
        ChatCompletionRequest(
            model="tao-sn1",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=16385,
        )


def test_request_max_tokens_at_upper_bound_accepted():
    from gateway.schemas.chat import ChatCompletionRequest

    req = ChatCompletionRequest(
        model="tao-sn1",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=16384,
    )
    assert req.max_tokens == 16384


def test_request_empty_model_rejected():
    from gateway.schemas.chat import ChatCompletionRequest

    with pytest.raises(ValidationError, match="model"):
        ChatCompletionRequest(
            model="",
            messages=[{"role": "user", "content": "Hello"}],
        )


def test_request_stream_default_false():
    from gateway.schemas.chat import ChatCompletionRequest

    req = ChatCompletionRequest(
        model="tao-sn1",
        messages=[{"role": "user", "content": "Hello"}],
    )
    assert req.stream is False


def test_response_schema_structure():
    from gateway.schemas.chat import ChatCompletionResponse, ChatMessage, Choice, CompletionUsage

    resp = ChatCompletionResponse(
        id="chatcmpl-abc123",
        object="chat.completion",
        created=1234567890,
        model="tao-sn1",
        choices=[
            Choice(
                index=0,
                message=ChatMessage(role="assistant", content="Hi there!"),
                finish_reason="stop",
            )
        ],
        usage=CompletionUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
    )
    assert resp.id == "chatcmpl-abc123"
    assert resp.object == "chat.completion"
    assert resp.choices[0].message.content == "Hi there!"
    assert resp.choices[0].finish_reason == "stop"


def test_response_schema_serialization():
    from gateway.schemas.chat import ChatCompletionResponse, ChatMessage, Choice, CompletionUsage

    resp = ChatCompletionResponse(
        id="chatcmpl-abc123",
        object="chat.completion",
        created=1234567890,
        model="tao-sn1",
        choices=[
            Choice(
                index=0,
                message=ChatMessage(role="assistant", content="Hi"),
                finish_reason="stop",
            )
        ],
        usage=CompletionUsage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
    )
    data = resp.model_dump()
    assert data["object"] == "chat.completion"
    assert data["usage"]["total_tokens"] == 8
    assert isinstance(data["choices"], list)


def test_chunk_schema_structure():
    from gateway.schemas.chat import ChatCompletionChunk, ChunkChoice, DeltaMessage

    chunk = ChatCompletionChunk(
        id="chatcmpl-abc123",
        object="chat.completion.chunk",
        created=1234567890,
        model="tao-sn1",
        choices=[
            ChunkChoice(
                index=0,
                delta=DeltaMessage(content="Hello"),
                finish_reason=None,
            )
        ],
    )
    assert chunk.object == "chat.completion.chunk"
    assert chunk.choices[0].delta.content == "Hello"
    assert chunk.choices[0].finish_reason is None


def test_chunk_schema_done():
    from gateway.schemas.chat import ChatCompletionChunk, ChunkChoice, DeltaMessage

    chunk = ChatCompletionChunk(
        id="chatcmpl-abc123",
        object="chat.completion.chunk",
        created=1234567890,
        model="tao-sn1",
        choices=[
            ChunkChoice(
                index=0,
                delta=DeltaMessage(),
                finish_reason="stop",
            )
        ],
    )
    assert chunk.choices[0].finish_reason == "stop"
    assert chunk.choices[0].delta.content is None
    assert chunk.choices[0].delta.role is None


def test_delta_message_partial_fields():
    from gateway.schemas.chat import DeltaMessage

    # Role only (first chunk convention)
    d1 = DeltaMessage(role="assistant")
    assert d1.role == "assistant"
    assert d1.content is None

    # Content only
    d2 = DeltaMessage(content="token")
    assert d2.role is None
    assert d2.content == "token"

    # Empty (done signal)
    d3 = DeltaMessage()
    assert d3.role is None
    assert d3.content is None


def test_chunk_schema_serialization():
    from gateway.schemas.chat import ChatCompletionChunk, ChunkChoice, DeltaMessage

    chunk = ChatCompletionChunk(
        id="chatcmpl-abc",
        object="chat.completion.chunk",
        created=1234567890,
        model="tao-sn1",
        choices=[
            ChunkChoice(
                index=0,
                delta=DeltaMessage(content="Hi"),
                finish_reason=None,
            )
        ],
    )
    data = chunk.model_dump()
    assert data["object"] == "chat.completion.chunk"
    assert data["choices"][0]["delta"]["content"] == "Hi"
