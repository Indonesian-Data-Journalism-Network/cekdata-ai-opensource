"""Conservative reading of explicit units; never infer a unit from the topic.

Stored units take precedence. Fallbacks only read unit labels on the same record,
and retain scale and provenance without changing the source value or metadata.
"""
from decimal import Decimal
import re

SCALES = {'': 1, 'ribu': 1000, 'juta': 1000000, 'miliar': 1000000000,
          'triliun': 1000000000000}
BASES = {'jiwa': 'jiwa', 'orang': 'jiwa', 'rupiah': 'rupiah', 'rp': 'rupiah',
         'ton': 'ton', 'hektar': 'ha', 'ha': 'ha', 'kasus': 'kasus',
         'rumah tangga': 'rumah tangga', 'keluarga': 'keluarga', 'unit': 'unit',
         'persen': 'persen', '%': 'persen', 'percent': 'persen',
         'tahun': 'tahun', 'indeks': 'indeks'}


def unit_parts(text):
    text = ' '.join(str(text).casefold().split())
    text = re.sub(r'^jumlah\s+', '', text)
    scale = next((s for s in SCALES if s and text.startswith(s + ' ')), '')
    base = BASES.get(text[len(scale):].strip())
    if base is None or (scale and base in {'persen', 'indeks', 'tahun'}):
        return None
    return base, SCALES[scale]


def convert_unit(value, from_unit, to_unit):
    """Exact scale conversion for known, identical base units; otherwise None."""
    left, right = unit_parts(from_unit), unit_parts(to_unit)
    if left is None or right is None or left[0] != right[0]:
        return None
    return Decimal(str(value)) * Decimal(left[1]) / Decimal(right[1])


def explicit_value_claim(question):
    """Read a single literal equality amount, not an inferred measurement unit."""
    q = question.casefold()
    if re.search(r'\b(?:dan|atau|tidak|bukan|kurang|lebih|setidaknya|maksimal|minimal|sekitar)\b', q):
        return None
    pattern = (r'\b(?:ada|sebanyak|sebesar|berjumlah|jumlahnya)\s+'
               r'(\d+(?:[.,]\d+)*)\s+'
               r'((?:(?:ribu|juta|miliar|triliun)\s+)?'
               r'(?:rumah tangga|jiwa|orang|rupiah|rp|ton|hektar|ha|kasus|keluarga|unit|persen|tahun|indeks))\b')
    matches = re.findall(pattern, q)
    if len(matches) != 1 or not unit_parts(matches[0][1]):
        return None
    value, unit = matches[0]
    # Indonesian numeric notation, consistent with the numeric claim fallback.
    return value.replace('.', '').replace(',', '.'), unit


def explicit_change_claim(question):
    """A stated change magnitude is equality, with sign from the direction."""
    q = question.casefold()
    if re.search(r'\b(?:dan|atau|tidak|bukan|kurang|lebih|setidaknya|maksimal|minimal|sekitar)\b', q):
        return None
    matches = re.findall(
        r'\b(naik|turun|meningkat|menurun|bertambah|berkurang)\s+(?:sebesar\s+)?'
        r'(\d+(?:[.,]\d+)*)\s+'
        r'(poin persentase|persen|percent|%|(?:(?:ribu|juta|miliar|triliun)\s+)?'
        r'(?:rumah tangga|jiwa|orang|rupiah|rp|ton|hektar|ha|kasus|keluarga|unit))(?=$|\W)', q)
    if len(matches) != 1:
        return None
    direction, raw, unit = matches[0]
    value = Decimal(raw.replace('.', '').replace(',', '.'))
    if direction in {'turun', 'menurun', 'berkurang'}:
        value = -value
    if unit in {'%', 'percent'}:
        unit = 'persen'
    return str(value), unit


def read_unit(metadata):
    stored = metadata.get('unit')
    if stored is not None and str(stored).strip():
        return str(stored), {}, ''
    candidates = []
    for field in ('title', 'table_title', 'series_label', 'unit_label', 'unit_note', 'definition'):
        text = metadata.get(field)
        if not isinstance(text, str):
            continue
        labels = re.findall(r'\(([^()]*)\)|\[([^\[\]]*)\]', text)
        labels = [a or b for a, b in labels]
        labels += re.findall(r'\b(?:satuan|unit)\s*:\s*([^;\n.]+)', text, re.I)
        if field in {'unit_label', 'unit_note'}:
            labels.append(text)
        for label in labels:
            parts = unit_parts(label)
            if parts:
                candidates.append((field, label.strip(), parts))
    if not candidates:
        return '', {}, 'missing_unit'
    if len({c[2] for c in candidates}) != 1:
        return '', {}, 'conflicting_unit_labels'
    field, label, (base, scale) = candidates[0]
    prefix = next(s for s, factor in SCALES.items() if factor == scale)
    unit = (prefix + ' ' + base).strip()
    return unit, {'mode': 'explicit_label_fallback', 'field': field,
                  'label': label, 'base_unit': base, 'scale': scale}, ''
