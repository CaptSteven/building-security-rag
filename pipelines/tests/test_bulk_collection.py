import pytest
pytest.importorskip('bs4',reason='collection dependency group not installed')
from pipelines.collection.bulk_collect import pdf_kind


def test_countable_pdf_types_exclude_padding_material():
    assert pdf_kind('AXIS Camera Datasheet','https://example.com/datasheet.pdf')=='datasheet'
    assert pdf_kind('Installation Guide','https://example.com/install.pdf')=='installation'
    assert pdf_kind('User Manual','https://example.com/um_camera.pdf')=='user_manual'
    assert pdf_kind('Wiring guide','https://example.com/wiring.pdf')=='wiring'
    for title in ['Declaration of conformity','Dimension drawing','Flyer','Product discontinuation statement','MTBF statement']:
        assert pdf_kind(title,'https://example.com/file.pdf') is None
