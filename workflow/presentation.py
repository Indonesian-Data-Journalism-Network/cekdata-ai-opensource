"""Text renderer reused from Cek Data AI, commit f6e24c35fb3a5111628187659209beebb146611a.
Keeps the existing parsed response contract and footer order.
"""
from typing import Any, Dict, List

def render_answer(parsed: Dict[str, Any]) -> str:
    """
    Render dict hasil analisis menjadi teks yang siap ditampilkan ke pengguna.

    Urutan section: Klaim → Temuan data → Kesimpulan (tren) → Konteks → Penilaian → Alasan
                    → Peringatan editorial → Sumber + Unduh data
    """
    if parsed.get("compact_message"):
        return str(parsed["compact_message"]).strip()

    sections: List[str] = []

    grouped = parsed.get('document_answer') and 'finding_groups' in parsed
    if grouped:
        from answer_format import markdown_table
        if parsed.get('claim'): sections.append('Klaim\n' + parsed['claim'])
        if parsed.get('penilaian'):
            sections.append('Penilaian: ' + parsed['penilaian'] + ('\n\n' + parsed['alasan'] if parsed.get('alasan') else ''))
        for group in parsed['finding_groups']:
            text = 'Temuan Data ' + group['source'] + '\n' + '\n'.join('- ' + point for point in group['findings'])
            if group.get('table'): text += '\n\n' + markdown_table(group['table'])
            sections.append(text)
        gfw = parsed.get('gfw_context')
        if gfw:
            sections.append('Temuan Data Global Forest Watch\n' + gfw['summary'] + '\n\n' + markdown_table(gfw['table']))
        if parsed.get('kesimpulan'): sections.append('Kesimpulan\n' + parsed['kesimpulan'])
        context = parsed.get('konteks_penting') or (gfw or {}).get('context')
        if context: sections.append('Konteks\n' + context)
        if parsed.get('peringatan_editorial'): sections.append('Peringatan Editorial\n' + parsed['peringatan_editorial'])
    elif parsed.get('answer_format') == 2:
        if parsed.get('claim'): sections.append('Klaim\n' + parsed['claim'])
        if parsed.get('penilaian'):
            sections.append('Penilaian: ' + parsed['penilaian'] + ('\n\n' + parsed['alasan'] if parsed.get('alasan') else ''))
        elif parsed.get('jawaban_utama'):
            sections.append(parsed['jawaban_utama'])
        table = parsed.get('findings_table')
        if table:
            from answer_format import markdown_table
            if parsed.get('document_answer') and parsed.get('temuan_data'):
                sections.append('Temuan Data\n'+parsed['temuan_data']+'\n\n'+markdown_table(table))
            else:
                sections.append('Temuan Data\n' + markdown_table(table))
        elif parsed.get('temuan_data'):
            sections.append('Temuan Data\n' + parsed['temuan_data'])
        for label,key in [('Konteks','konteks_penting'),('Peringatan editorial','peringatan_editorial')]:
            if parsed.get(key): sections.append(label+'\n'+parsed[key])
    else:
        for label,key in [('Klaim','claim'),('Penilaian','penilaian'),('Alasan','alasan'),
                          ('Kesimpulan','kesimpulan'),('Temuan Data','temuan_data'),
                          ('Konteks','konteks_penting'),('Peringatan editorial','peringatan_editorial')]:
            if parsed.get(key): sections.append(label+'\n'+str(parsed[key]))

    for group in parsed.get('related_evidence', []):
        from answer_format import markdown_table
        text = 'Temuan Data Terkait\n' + group['summary'] + '\n\n' + markdown_table(group['table'])
        text += '\n\nKonteks\n' + group['context']
        seen = set()
        for source in group['parsed']['source_items']:
            key = (source['display'], source['url'], source.get('dataset_version'))
            if key in seen: continue
            seen.add(key)
            version = ' — versi ' + source['dataset_version'] if source.get('dataset_version') else ''
            text += '\n\nSumber: ' + source['display'] + version + '\n' + source['url']
            if source.get('download_url') and 'data-api.globalforestwatch.org/' not in source['download_url']:
                text += '\nUnduh: ' + source['title'] + '\n' + source['download_url']
        sections.append(text)
    if parsed.get('related_evidence_status') == 'service_unavailable':
        sections.append('Pencarian data terkait belum selesai karena gangguan layanan. Ini bukan tanda bahwa datanya tidak tersedia.')

    footer: List[str] = []
    if not parsed.get('document_answer') and any(item.get('source_record_id', '').startswith('mapbiomas:')
                                               for item in parsed.get('source_items', [])):
        seen = set()
        for item in parsed.get('source_items', []):
            is_map = item.get('source_record_id', '').startswith('mapbiomas:')
            version = item.get('dataset_version') or (item.get('source_record_id', '').split(':') + ['', '', ''])[2]
            key = (item.get('source'), version, item.get('url'))
            if key in seen:
                continue
            seen.add(key)
            label = f"{item.get('source', '')} — {'Koleksi' if is_map else 'versi'} {version}"
            footer.append(f"Sumber: {label}\n{item.get('url', '')}")
            if is_map:
                footer.append(f"Unduh: Tutupan dan transisi lahan Indonesia — Koleksi {version} (XLSX)\n{item.get('download_url', '')}")
        if footer:
            sections.append('\n'.join(footer))
        return '\n\n'.join(sections).strip()
    if parsed.get('document_answer'):
        gfw = parsed.get('gfw_context') or {}
        if gfw and not grouped:
            from answer_format import markdown_table
            sections.append('Data Global Forest Watch\n' + gfw['summary'] + '\n\n' + markdown_table(gfw['table']) + '\n\n' + gfw['context'])
        for item in parsed.get('source_items', []):
            pages = ', '.join(str(p) for p in item.get('pdf_pages', []))
            number=f"[{item['source_number']}] " if item.get('source_number') else ''
            footer.append(f"{number}Sumber: {item['display']}" + (f" — halaman PDF {pages}" if pages else '') + f"\n{item['url']}")
            footer.append(f"Unduh: {item['title']} (PDF)\n{item['download_url']}")
        seen_gfw=set()
        for item in (gfw.get('parsed') or {}).get('source_items', []):
            key=(item.get('display','Global Forest Watch'),item.get('url',''))
            if key not in seen_gfw:
                seen_gfw.add(key)
                footer.append(f"Sumber: {key[0]}\n{key[1]}")
        if footer: sections.append('\n'.join(footer))
        return '\n\n'.join(sections).strip()
    if parsed.get("sumber"):
        footer.append(f"Sumber: {parsed['sumber']}")

    link_sumber = parsed.get("link_sumber")
    if link_sumber:
        if isinstance(link_sumber, list):
            if len(link_sumber) == 1:
                footer.append(f"Link sumber: {link_sumber[0]}")
            else:
                footer.append("Link sumber:")
                footer.extend(f"* {item}" for item in link_sumber)
        else:
            footer.append(f"Link sumber: {link_sumber}")

    methodology = list(dict.fromkeys(item.get('methodology_url') for item in parsed.get('source_items', [])
                                    if item.get('methodology_url')))
    if methodology:
        footer.append('Dataset dasar dan metode: ' + '; '.join(methodology))

    unduh = parsed.get("unduh_data")
    if unduh:
        if isinstance(unduh, list):
            if len(unduh) == 1:
                footer.append(f"Unduh data: {unduh[0]}")
            else:
                footer.append("Unduh data:")
                footer.extend(f"* {item}" for item in unduh)
        else:
            footer.append(f"Unduh data: {unduh}")

    if footer:
        sections.append("\n".join(footer))

    # Followup prompt — ajakan untuk menyampaikan konteks klaim
    if parsed.get("followup_prompt"):
        sections.append(f"{parsed['followup_prompt']}")

    return "\n\n".join(s for s in sections if s).strip()
