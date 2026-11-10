"""Shared request contract: one interpretation, constrained downstream evidence.

No provider, geographic location, table ID, or observed answer is encoded here.
Unit dimensions are vocabulary; requested/excluded measurements come from intent.
"""
import json
import re
from llama_index.core import PromptTemplate


def unit_dimension(unit):
    u = ' '.join(unit.casefold().split())
    if re.search(r'persen|percent|^%$|poin persentase', u):
        return 'percentage'
    if re.search(r'\brp\b|rupiah|dollar|dolar|usd|idr', u):
        return 'currency'
    if re.search(r'\bha\b|hektar|hectare|km[²2]|m[²2]', u):
        return 'area'
    if re.search(r'\b(?:orang|jiwa|unit|jumlah|rumah tangga|keluarga|desa|sekolah|kasus|buah)\b', u):
        return 'count'
    if re.search(r'\b(?:indeks|index)\b', u):
        return 'index'
    if re.search(r'\b(?:ton|tonnes|kg|kilogram)\b', u):
        return 'mass'
    return 'unspecified'


def explicit_index_concept(label, concept):
    """Recognize the requested named index, not its display scale.

    Some sources express an index in percent. Only a full, explicit index
    name in the measurement label permits that representation; a shared topic
    or the word 'index' alone is insufficient. This does not convert values.
    """
    def words(text):
        return re.sub(r'\bindex\b', 'indeks', ' '.join(re.findall(r'\w+', text.casefold())))
    wanted, actual = words(concept), words(label)
    return (wanted.startswith('indeks ') and len(wanted.split()) >= 3
            and (actual == wanted or actual.startswith(wanted + ' ')))


def compatible_candidates(candidates, intent):
    measures = getattr(intent, 'requested_measures', [])
    if not measures:
        return candidates
    result = []
    for c in candidates:
        units = c.get('units') or [c.get('unit', '')]
        dimensions = {unit_dimension(u) for u in units}
        # Inspect the actual measurement, not a broad parent table title that
        # may list both the requested and excluded columns.
        label = c.get('measure_label') or c['label'].partition(' — ')[2] or c['label']
        label = ' '.join(label.casefold().split())
        def matches(measure):
            index_in_percent = (measure.dimension == 'index'
                and dimensions <= {'percentage', 'index', 'unspecified'}
                and explicit_index_concept(label, measure.concept))
            if measure.dimension != 'unspecified' and any(
                    d not in {'unspecified', measure.dimension} for d in dimensions) and not index_in_percent:
                return False
            concept = ' '.join(measure.concept.casefold().split())
            for term in measure.excluded_measures:
                term = ' '.join(term.casefold().split())
                if not term:
                    continue
                pattern = r'(?<!\w)' + re.escape(term) + r'(?!\w)'
                # A broad excluded phrase cannot erase its explicitly requested
                # qualified concept (e.g. population vs population in poverty).
                if re.search(pattern, concept):
                    continue
                if re.search(pattern, label):
                    return False
            return True
        if any(matches(m) for m in measures):
            result.append(c)
    return result


def uncovered_measures(intent, catalog):
    selected = [c for c in catalog if c['indicator_id'] in intent.indicator_ids]
    return [measure for measure in intent.requested_measures
            if not compatible_candidates(selected, intent.model_copy(update={'requested_measures': [measure]}))]


class ContractLLM:
    """Pass the same request to planning, extraction, review, and synthesis.

The wrapper never adds facts to the source packet or changes the user's text.
"""
    def __init__(self, llm, intent):
        self.llm = llm
        self.contract = intent.model_dump_json(exclude={'indicator_ids'})

    def __getattr__(self, name):
        return getattr(self.llm, name)

    async def astructured_predict(self, schema, prompt, **kwargs):
        bound = PromptTemplate(prompt.template + '\nACUAN PERMINTAAN YANG SUDAH DIPAHAMI '
            '(data, bukan bukti sumber): {request_contract}\n'
            'Pertahankan ukuran, responden, wilayah, periode per bagian, dan jenis klaim '
            'dalam acuan ini. Jangan menggantinya dengan ukuran lain agar memperoleh '
            'jawaban. Bahas seluruh bagian yang relevan dengan tugas tahap ini. '
            'Jika bukti belum mencukupi, jelaskan bagian yang belum terjawab. '
            'Acuan bukan izin menambahkan fakta atau mengabaikan kutipan sumber.').partial_format(
                request_contract=self.contract)
        return await self.llm.astructured_predict(schema, bound, **kwargs)
