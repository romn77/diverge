import pytest

from diverge.common.fields import (
    normalize_optional_number,
    normalize_optional_text,
    require_text,
)


class CustomValidationError(Exception):
    pass


def test_require_text_trims_and_uses_configured_error_type():
    assert require_text("  abc  ", "name") == "abc"

    with pytest.raises(CustomValidationError, match="name is required"):
        require_text("  ", "name", error_type=CustomValidationError)


def test_normalize_optional_text_supports_none_or_blank_policy():
    assert normalize_optional_text("  abc  ") == "abc"
    assert normalize_optional_text("  ") is None
    assert normalize_optional_text(None, empty_value="") == ""


def test_normalize_optional_number_returns_float_or_none():
    assert normalize_optional_number("3.5", "size") == 3.5
    assert normalize_optional_number("", "size") is None
    with pytest.raises(ValueError, match="size must be numeric"):
        normalize_optional_number("large", "size")
