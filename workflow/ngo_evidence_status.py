"""Preserve evidentiary status without encoding places, publishers or answers.

This is a backstop for source review, not an independent semantic classifier.
Only clauses that reuse source content are compared; unrelated warnings in a
report do not change the status of an observed event elsewhere in that report.
"""
import re

MARKERS = {
    'rencana': r'\b(?:rencana\w*|direncanakan|berencana|akan|planned|planning|proposed|proposal)\b',
    'risiko': r'\b(?:risiko|resiko|berisiko|berpotensi|potensi|terancam|ancaman|mengancam|dapat|bisa|risk\w*|potential\w*|threat\w*|could)\b|\bmay\s+(?:cause|lead|result|increase|decrease|affect|displace)\b',
    'analisis penerbit': r'\b(?:menilai|penilaian|berpendapat|berpandangan|argues?|opinion|interprets?|interpretasi)\b',
    'hasil pemodelan/proyeksi': r'\b(?:pemodelan|simulasi|skenario|proyeksi|diproyeksi\w*|modeling|modelling|simulation|scenario|projected)\b',
}
PATTERNS = {name: re.compile(pattern, re.I) for name,pattern in MARKERS.items()}
RESPONDENT_OPINION = re.compile(
    r'\b(?:saya|kami|warga|masyarakat|responden|narasumber|pekerja|petani|nelayan|'
    r'respondents?|residents?|workers?|farmers?|fishers?)\s+'
    r'(?:(?:yang\s+diwawancarai|setempat|terdampak|lokal|survei|surveyed|local)\s+)?'
    r'(?:menilai|berpendapat|berpandangan|menganggap|merasa|believe[sd]?|feel|felt)\b', re.I)
# Negated ability describes an experienced restriction, not a forecast. Keep
# explicit risk/future words in the sentence so hypothetical losses stay risks.
INABILITY = re.compile(
    r'\b(?:tidak|tak|belum|sudah\s+tidak)\s+(?:lagi\s+)?(?:bisa|dapat)\s+(?:lagi\s+)?'
    r'(?!(?:dipastikan|disimpulkan|dibuktikan|diketahui|ditentukan|dikonfirmasi|diprediksi|diperkirakan)\b)'
    r'(?=\w)', re.I)
STOP = set('yang dan atau dalam dari pada untuk dengan oleh adalah merupakan telah sudah menjadi ini itu tersebut laporan menurut sebagai bahwa suatu sebuah terhadap karena juga belum tidak bukan'.split())


def clauses(text):
    return [s.strip() for s in re.split(r'(?<=[.!?;])\s+|\s+(?:namun|tetapi|sedangkan|whereas|however)\s+',text) if s.strip()]


def status_tags(text):
    text=INABILITY.sub('',text)
    opinion=bool(RESPONDENT_OPINION.search(text))
    publisher_text=RESPONDENT_OPINION.sub('',text)
    tags={name for name,pattern in PATTERNS.items()
          if pattern.search(publisher_text if name=='analisis penerbit' else text)}
    if opinion:tags.add('penilaian responden')
    return tags


def content_words(text):
    for pattern in PATTERNS.values(): text=pattern.sub(' ',text)
    return set(re.findall(r'\b[^\W\d_]{4,}\b',text.casefold()))-STOP


def status_errors(text, source):
    """Reject lost modality on the closest source clause, including no-number prose."""
    errors=[]
    originals=clauses(source)
    for sentence in clauses(text):
        # A statement of evidentiary limits does not assert that an event occurred.
        if re.search(r'\b(?:belum|tidak) (?:membuktikan|dapat disimpulkan|cukup|dapat dipastikan)\b|\bbukan bukti\b',sentence,re.I):continue
        words=content_words(sentence)
        ranked=[(len(words & content_words(s)),s) for s in originals]
        best=max((n for n,_ in ranked),default=0)
        if best<2:continue
        closest=[s for n,s in ranked if n==best]
        # An observed clause with equally strong support remains observed.
        required=set.intersection(*(status_tags(s) for s in closest))
        missing=required-status_tags(sentence)
        errors.extend(f'Pertahankan status {tag} dari sumber; jangan menyajikannya sebagai kejadian yang telah terbukti.' for tag in sorted(missing))
    return list(dict.fromkeys(errors))


def universal_kind(question):
    """Return logical scope, not a verdict. Quantifiers alone prove nothing."""
    if re.search(r'\b(?:tidak|tak|bukan)\s+(?:semua|seluruh|setiap)\b',question,re.I):return 'not_all'
    if re.search(r'\b(?:tidak|tak)\s+ada\b|\btidak satu pun\b|\bnol\b|\b0\s*(?:ha|hektar|persen|%|orang|rumah tangga)\b',question,re.I):return 'none'
    if re.search(r'\b(?:semua|seluruh|setiap|all|every)\b|\b100\s*(?:persen|%)',question,re.I):return 'all'
    return ''
