import io

from app.services.ingest import workbook


def count(xml: bytes, chunk: int | None = None) -> int:
    if chunk:
        workbook._SCAN_CHUNK, saved = chunk, workbook._SCAN_CHUNK
        try:
            return workbook._count_uncached_formulas(io.BytesIO(xml))
        finally:
            workbook._SCAN_CHUNK = saved
    return workbook._count_uncached_formulas(io.BytesIO(xml))


SHEET = (
    b'<worksheet><sheetData><row r="1">'
    b'<c r="A1" t="s"><v>0</v></c>'  # plain value
    b'<c r="B1"><f>A1*2</f><v>4</v></c>'  # formula with cached value
    b'<c r="C1"><f>A1*3</f></c>'  # formula without cached value
    b'<c r="D1"><f>A1*4</f><v></v></c>'  # empty cached value
    b'<c r="E1" s="1"/>'  # empty styled cell
    b'<c r="F1"><f t="shared" si="0"/></c>'  # shared formula, no cache
    b'<c r="G1" t="str"><f>"x"</f><v>x</v></c>'
    b"</row></sheetData></worksheet>"
)


def test_counts_only_formulas_without_saved_values():
    assert count(SHEET) == 3


def test_chunk_boundaries_do_not_change_the_result():
    for size in (7, 13, 64, 100):
        assert count(SHEET, chunk=size) == 3, size


def test_namespace_prefixed_markup():
    xml = b'<x:worksheet><x:c r="A1"><x:f>1+1</x:f></x:c><x:c r="A2"><x:f>1</x:f><x:v>1</x:v></x:c></x:worksheet>'
    assert count(xml) == 1


def test_no_formulas_short_circuits():
    assert count(b'<worksheet><c r="A1"><v>1</v></c><c r="A2" t="inlineStr"><is><t>f</t></is></c></worksheet>') == 0
