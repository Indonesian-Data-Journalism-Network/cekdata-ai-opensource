"""Text renderer reused from Cek Data AI, commit f6e24c35fb3a5111628187659209beebb146611a.
Keeps the existing parsed response contract and footer order.
"""
from typing import Any, Dict, List

def render_answer(parsed: Dict[str, Any]) -> str:
    """
    Render dict hasil analisis menjadi teks yang siap ditampilkan ke pengguna.

    Urutan section: Klaim → Temuan data → Kesimpulan (tren) → Konteks penting → Penilaian → Alasan
                    → Peringatan editorial → Sumber + Unduh data
    """
    if parsed.get("compact_message"):
        return str(parsed["compact_message"]).strip()

    sections: List[str] = []

    for label, key in [
        ("Klaim", "claim"),
        ("Temuan data", "temuan_data"),
        ("Kesimpulan", "kesimpulan"),
        ("Konteks penting", "konteks_penting"),
        ("Penilaian", "penilaian"),
        ("Alasan", "alasan"),
        ("Peringatan editorial", "peringatan_editorial"),
    ]:
        value = parsed.get(key)
        if value:
            sections.append(f"{label}\n{value}")

    footer: List[str] = []
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
