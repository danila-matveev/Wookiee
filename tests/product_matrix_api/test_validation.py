"""Tests for cascade validation rules and impact checking."""
import pytest

from services.product_matrix_api.services.validation import (
    CASCADE_RULES,
    ValidationService,
)


def test_cascade_rules_has_modeli_osnova():
    assert "modeli_osnova" in CASCADE_RULES
    assert CASCADE_RULES["modeli_osnova"]["strategy"] == "cascade_archive"


def test_cascade_rules_has_cveta():
    assert "cveta" in CASCADE_RULES
    assert CASCADE_RULES["cveta"]["strategy"] == "block_if_active"


def test_cascade_rules_has_fabriki():
    assert "fabriki" in CASCADE_RULES
    assert CASCADE_RULES["fabriki"]["strategy"] == "block_if_active"


def test_simple_entity_returns_simple():
    """Entities not in CASCADE_RULES default to 'simple' strategy."""
    strategy = ValidationService.get_strategy("sertifikaty")
    assert strategy == "simple"


def test_cascade_entity_returns_cascade():
    strategy = ValidationService.get_strategy("modeli_osnova")
    assert strategy == "cascade_archive"


def test_block_entity_returns_block():
    strategy = ValidationService.get_strategy("cveta")
    assert strategy == "block_if_active"


def test_generate_challenge():
    """Challenge generates a math problem and correct answer hash."""
    challenge_text, expected_hash, salt = ValidationService.generate_challenge()
    # Challenge should be in format "X × Y"
    assert "×" in challenge_text
    parts = challenge_text.split("×")
    a, b = int(parts[0].strip()), int(parts[1].strip())
    answer = str(a * b)
    # Hash should be sha256(answer + salt)
    import hashlib
    expected = hashlib.sha256(f"{answer}{salt}".encode()).hexdigest()
    assert expected_hash == expected


def test_verify_challenge_correct():
    challenge_text, expected_hash, salt = ValidationService.generate_challenge()
    parts = challenge_text.split("×")
    a, b = int(parts[0].strip()), int(parts[1].strip())
    answer = str(a * b)
    assert ValidationService.verify_challenge(answer, expected_hash, salt) is True


def test_verify_challenge_wrong():
    _, expected_hash, salt = ValidationService.generate_challenge()
    assert ValidationService.verify_challenge("99999", expected_hash, salt) is False
