import pytest

from services.user_input_security import (
    normalize_registration_input,
    validate_login_input,
    validate_password_reset_input,
)


def test_registration_normalizes_email_and_accepts_international_phone():
    item = normalize_registration_input(
        username="  测试_user-1  ",
        password="A secure passphrase 123",
        phone=" +49 151 23456789 ",
        email=" USER@Example.COM ",
    )
    assert item.username == "测试_user-1"
    assert item.email == "user@example.com"
    assert item.phone == "+4915123456789"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("username", "ab", "用户名至少"),
        ("username", "a" * 65, "用户名最多"),
        ("username", "bad/name", "用户名只能"),
        ("password", "x" * 129, "密码最多"),
        ("email", "not-an-email", "邮箱格式"),
        ("email", "a" * 250 + "@x.com", "邮箱最多"),
        ("phone", "+12", "手机号格式"),
        ("phone", "+49123\n456", "控制字符"),
    ],
)
def test_registration_rejects_unsafe_boundaries(field, value, message):
    kwargs = {
        "username": "safe_user",
        "password": "A secure passphrase 123",
        "phone": "+4915123456789",
        "email": "safe@example.com",
    }
    kwargs[field] = value
    with pytest.raises(ValueError, match=message):
        normalize_registration_input(**kwargs)


def test_registration_requires_contact():
    with pytest.raises(ValueError, match="至少填写邮箱或手机号"):
        normalize_registration_input(
            username="safe_user",
            password="A secure passphrase 123",
            phone="",
            email="",
        )


def test_login_and_password_reset_inputs_are_bounded():
    assert validate_login_input(" user@example.com ", "secret") == ("user@example.com", "secret")
    assert validate_password_reset_input(" user ", "mail@example.com") == ("user", "mail@example.com")
    with pytest.raises(ValueError, match="账号最多"):
        validate_login_input("x" * 255, "secret")
    with pytest.raises(ValueError, match="密码最多"):
        validate_login_input("user", "x" * 129)
    with pytest.raises(ValueError, match="联系方式最多"):
        validate_password_reset_input("user", "x" * 255)
