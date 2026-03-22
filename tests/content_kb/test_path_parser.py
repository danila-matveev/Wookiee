"""Tests for content_kb path_parser."""

from services.content_kb.path_parser import parse_path_metadata


def test_marketplace_full_path():
    result = parse_path_metadata(
        "/Контент/2025/5. МАРКЕТПЛЕЙСЫ/Bella/Bella-black/257144777/01.png"
    )
    assert result["year"] == 2025
    assert result["content_category"] == "маркетплейсы"
    assert result["model_name"] == "Bella"
    assert result["color"] == "black"
    assert result["sku"] == "257144777"


def test_photo_path():
    result = parse_path_metadata(
        "/Контент/2025/1. ВСЕ ФОТО/1. Готовый контент/Bella/1. Основные/Bella-black/photo.jpg"
    )
    assert result["year"] == 2025
    assert result["content_category"] == "фото"
    assert result["model_name"] == "Bella"
    assert result["color"] == "black"
    assert result["sku"] is None


def test_bloggers_path():
    result = parse_path_metadata("/Блогеры/Реклама блогеров/campaign_1/photo.jpg")
    assert result["content_category"] == "блогеры"
    assert result["model_name"] is None


def test_design_path():
    result = parse_path_metadata("/Контент/2025/4. ДИЗАЙН/banners/img.png")
    assert result["content_category"] == "дизайн"


def test_set_model():
    result = parse_path_metadata(
        "/Контент/2025/5. МАРКЕТПЛЕЙСЫ/set_Bella/set_Bella-white/123/01.png"
    )
    assert result["model_name"] == "set_Bella"
    assert result["color"] == "white"


def test_ab_test_path():
    result = parse_path_metadata(
        "/Контент/2025/7. АБ тесты /Сентябрь/Bella/variant_a.png"
    )
    assert result["content_category"] == "аб_тесты"
    assert result["model_name"] == "Bella"


def test_color_extraction_from_compound_name():
    """Bella-light_beige → model=Bella, color=light_beige"""
    result = parse_path_metadata(
        "/Контент/2025/5. МАРКЕТПЛЕЙСЫ/Bella/Bella-light_beige/123/01.png"
    )
    assert result["model_name"] == "Bella"
    assert result["color"] == "light_beige"


def test_lamoda_path():
    result = parse_path_metadata("/Контент/2025/8. LAMODA/Bella/photo.jpg")
    assert result["content_category"] == "lamoda"
    assert result["model_name"] == "Bella"
