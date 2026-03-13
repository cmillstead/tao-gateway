from argon2 import PasswordHasher

from gateway.services.api_key_service import generate_api_key

ph = PasswordHasher()


def test_generate_api_key_live_format() -> None:
    full_key, prefix, key_hash = generate_api_key("live")
    assert full_key.startswith("tao_sk_live_")
    assert len(prefix) == 20
    assert full_key[:20] == prefix
    assert key_hash != full_key


def test_generate_api_key_test_format() -> None:
    full_key, prefix, key_hash = generate_api_key("test")
    assert full_key.startswith("tao_sk_test_")
    assert len(prefix) == 20


def test_generate_api_key_hash_is_argon2() -> None:
    full_key, _prefix, key_hash = generate_api_key("live")
    assert key_hash.startswith("$argon2")
    # Verify hash matches the key
    assert ph.verify(key_hash, full_key)


def test_generate_api_key_uniqueness() -> None:
    key1 = generate_api_key("live")
    key2 = generate_api_key("live")
    assert key1[0] != key2[0]  # full keys differ
    assert key1[1] != key2[1]  # prefixes differ
    assert key1[2] != key2[2]  # hashes differ


def test_generate_api_key_hash_not_plaintext() -> None:
    full_key, _prefix, key_hash = generate_api_key("live")
    assert full_key not in key_hash
