from app.security import hash_password, verify_password


def test_hash_password_does_not_return_plaintext():
    password = "example-test-password"

    password_hash = hash_password(password)

    assert password_hash != password
    assert password_hash.startswith("$argon2id$")


def test_verify_password_accepts_correct_and_rejects_wrong_password():
    password = "example-test-password"
    password_hash = hash_password(password)

    assert verify_password(password, password_hash) is True
    assert verify_password("incorrect-password", password_hash) is False


def test_hash_password_uses_random_salts():
    password = "example-test-password"

    first_hash = hash_password(password)
    second_hash = hash_password(password)

    assert first_hash != second_hash
    assert verify_password(password, first_hash) is True
    assert verify_password(password, second_hash) is True
