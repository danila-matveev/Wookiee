"""Validate Phase 3 Pydantic schemas instantiate correctly."""
from services.product_matrix_api.models.schemas import (
    ArtikulCreate, ArtikulRead,
    TovarCreate, TovarRead,
    CvetCreate, CvetRead,
    FabrikaCreate, FabrikaRead,
    ImporterCreate, ImporterRead,
    SleykaWBCreate, SleykaWBRead,
    SleykaOzonCreate, SleykaOzonRead,
    SertifikatCreate, SertifikatRead,
    SearchResult, SearchResponse,
    BulkActionRequest,
)


def test_artikul_schemas():
    c = ArtikulCreate(artikul="Vuki/Black")
    assert c.artikul == "Vuki/Black"
    r = ArtikulRead(id=1, artikul="Vuki/Black")
    assert r.id == 1


def test_tovar_schemas():
    c = TovarCreate(barkod="4670437802315")
    assert c.barkod == "4670437802315"
    r = TovarRead(id=1, barkod="4670437802315")
    assert r.id == 1


def test_cvet_schemas():
    c = CvetCreate(color_code="BLK")
    assert c.color_code == "BLK"
    r = CvetRead(id=1, color_code="BLK")
    assert r.id == 1


def test_fabrika_schemas():
    c = FabrikaCreate(nazvanie="Shanghai Factory")
    assert c.nazvanie == "Shanghai Factory"
    r = FabrikaRead(id=1, nazvanie="Shanghai Factory")
    assert r.id == 1


def test_importer_schemas():
    c = ImporterCreate(nazvanie="ИП Иванов")
    assert c.nazvanie == "ИП Иванов"
    r = ImporterRead(id=1, nazvanie="ИП Иванов")
    assert r.id == 1


def test_skleyka_wb_schemas():
    c = SleykaWBCreate(nazvanie="Vuki WB card")
    assert c.nazvanie == "Vuki WB card"
    r = SleykaWBRead(id=1, nazvanie="Vuki WB card")
    assert r.id == 1


def test_skleyka_ozon_schemas():
    c = SleykaOzonCreate(nazvanie="Vuki Ozon card")
    assert c.nazvanie == "Vuki Ozon card"
    r = SleykaOzonRead(id=1, nazvanie="Vuki Ozon card")
    assert r.id == 1


def test_sertifikat_schemas():
    c = SertifikatCreate(nazvanie="EAC Declaration")
    assert c.nazvanie == "EAC Declaration"
    r = SertifikatRead(id=1, nazvanie="EAC Declaration")
    assert r.id == 1


def test_search_result():
    r = SearchResult(entity="artikuly", id=1, name="Vuki/Black", match_field="artikul", match_text="Vuki/Black")
    assert r.entity == "artikuly"


def test_bulk_action():
    b = BulkActionRequest(ids=[1, 2, 3], action="update", changes={"status_id": 1})
    assert len(b.ids) == 3
