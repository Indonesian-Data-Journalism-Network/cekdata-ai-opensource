"""BPS source dimensions to the shared statistical-evidence payload.

Source identifiers/labels are retained separately. No value rescaling, inferred
observation years, or substitution between administrative boundary systems.
"""
import calendar
from decimal import Decimal
import html
import re

from tools.bps.client import BPSError

SCHEMA = 'cekdata-statistical-observation-v2'
MONTHS = ['', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
          'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']


def period_fields(year, label):
    text = label.strip()
    q = re.fullmatch(r'(?:Triwulan|Kuartal)\s+(IV|III|II|I|[1-4])', text, re.I)
    month = quarter = None
    if q:
        quarter = {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4}.get(q[1].casefold()) or int(q[1])
        basis, first, last = 'quarter', quarter * 3 - 2, quarter * 3
        period_text = f'Triwulan {("I", "II", "III", "IV")[quarter-1]} {year}'
    else:
        # "Semester 1 (Maret)" is the source's March observation, not a
        # January–June sum. Only these explicit source forms are accepted.
        month = next((i for i, name in enumerate(MONTHS[1:], 1)
                      if re.fullmatch(re.escape(name), text, re.I) or
                      re.fullmatch(r'Semester\s+[12]\s*\(' + re.escape(name) + r'\)', text, re.I)), None)
        if month:
            basis, first, last = 'month', month, month
            period_text = f'{MONTHS[month]} {year}'
        elif text.casefold() in {'tahun', 'tahunan', str(year)}:
            basis, first, last, period_text = 'annual', 1, 12, ''
        else:
            raise BPSError(f'Periode sumber belum dapat dipetakan: {text}')
    return dict(year=year, month=month, quarter=quarter, temporal_basis=basis,
                period_text=period_text, period_label_raw=label,
                period_start=f'{year}-{first:02d}-01',
                period_end=f'{year}-{last:02d}-{calendar.monthrange(year,last)[1]:02d}',
                aggregation_kind='')  # Frequency alone does not establish sum/mean/stock.


def unit_fields(unit):
    key = re.sub(r'\s+', ' ', unit.strip().casefold())
    known = {'persen': ('persen', 'percent', '1'), '%': ('persen', 'percent', '1'),
             'percent': ('persen', 'percent', '1'),
             'ribu jiwa': ('ribu jiwa', 'person', '1000'),
             'jiwa': ('jiwa', 'person', '1'),
             'orang': ('orang', 'person', '1'),
             'milyar rupiah': ('miliar rupiah', 'IDR', '1000000000'),
             'miliar rupiah': ('miliar rupiah', 'IDR', '1000000000'),
             'rupiah': ('rupiah', 'IDR', '1')}
    if key not in known:
        raise BPSError(f'Satuan belum dipetakan: {unit}')
    label, code, scale = known[key]
    return dict(unit=label, unit_code=code, unit_scale=scale, unit_source=unit)


def area_label(label):
    """Remove presentation markup, retaining the source label in original_row."""
    text = re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', '', label))).strip()
    text = re.sub(r'\bKep\.\s*', 'Kepulauan ', text, flags=re.I)
    text = re.sub(r'\b(?:[A-Z] ){1,3}[A-Z]\b', lambda m: m[0].replace(' ', ''), text)
    return text


def province_reference(payloads):
    result = {}
    for p in payloads:
        if 'provinsi' not in p['vertical_axis'].casefold() or p['vertical_label'].casefold() == 'indonesia':
            continue
        code = str(p['vertical_id'])
        if re.fullmatch(r'\d{2}(?:00)?', code):
            # Use a source table's province label, not an invented name lookup.
            label = area_label(p['vertical_label'])
            prior = result.get(code[:2])
            if prior and prior.casefold() != label.casefold():
                raise BPSError('Label provinsi sumber bertentangan; perlu rekonsiliasi.')
            result[code[:2]] = label
    return result


def standardize(p, provinces):
    row = dict(p)
    original = {k: v for k, v in p.items() if k not in {
        'schema_version', 'source', 'indicator_id', 'title', 'year', 'source_url',
        'source_snapshot_sha256', 'retrieved_at', 'vertical_key', 'period_text', 'provider', 'source_record_id'}}
    # The original BPS observation ID differs from its stable Qdrant UUID.
    original['id'] = p['source_record_id']
    area, code, axis = area_label(p['vertical_label']), str(p['vertical_id']), p['vertical_axis'].casefold()
    level, boundary_type, province = '', '', ''
    if area.casefold() == 'indonesia' and 'provinsi' in axis:
        level, boundary_type = 'adm0', 'Negara'
    elif 'provinsi' in axis and re.fullmatch(r'\d{2}(?:00)?', code):
        level, boundary_type, province = 'adm1', 'Provinsi', area
    elif 'kabupaten' in axis and 'kota' in axis:
        level = 'adm2'
        if not re.fullmatch(r'\d{4}', code) or code[:2] not in provinces:
            raise BPSError('Induk provinsi belum terpetakan pada kode wilayah BPS.')
        province = provinces[code[:2]]
        boundary_type = 'Kota' if re.match(r'^Kota\b', area, re.I) else 'Kabupaten'
    elif 'provinsi' in axis:
        level, boundary_type, province = 'adm1', 'Provinsi', area
    else:
        raise BPSError('Sumbu vertikal belum terverifikasi sebagai wilayah.')
    category = p['derived_label'].strip()
    label = p['title'] + (' — ' + category if category.casefold() not in {'tidak ada', ''} else '')
    population = {'perkotaan': 'urban', 'perdesaan': 'rural'}.get(category.casefold(), 'total')
    notes = html.unescape(re.sub('<[^>]+>', '\n', p.get('notes') or ''))
    notes = '\n'.join(x.strip() for x in notes.splitlines() if x.strip())
    year_note = re.search(r'(?:Tahun\s+)?' + str(p['year']) + r'\s*:\s*([^\n]+)', notes, re.I)
    status_note = year_note[1].strip() if year_note else ''
    data_status = 'provisional' if re.search(r'\bsementara\b', status_note, re.I) else 'published_status_unspecified'
    row.update(schema_version=SCHEMA, indicator=label, area=area, area_key=area.casefold(),
               area_code=code, area_code_system='BPS', geographic_level=level,
               boundary_type=boundary_type, province_context=province,
               province_code=(code[:2] if level in {'adm1','adm2'} else ''),
               source_name=p['source'], method='', population=population,
               population_label=(category if population != 'total' else ''),
               category_id=p['derived_id'], category_label=category,
               source_note=notes, data_status=data_status, data_status_note=status_note,
               usable=True, synthetic=False, download_url='',
               source_sha256=p['source_snapshot_sha256'], original_row=original,
               source_locator={k: p[k] for k in ('domain','variable_id','vertical_id','derived_id','period_id','subperiod_id','source_cell')},
               **period_fields(p['year'], p['subperiod_label']), **unit_fields(p['unit']))
    if not Decimal(row['value']).is_finite():
        raise BPSError('Nilai observasi tidak valid.')
    return row
