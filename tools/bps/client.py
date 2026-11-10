"""Read-only, bounded BPS API client; credentials never enter diagnostics/cache keys."""
import json
import re
import time
from urllib.parse import quote

import httpx


class BPSError(RuntimeError):
    pass


class BPSClient:
    def __init__(self, key, *, transport=None, interval=3.2):
        self._key = key.strip()
        if not self._key:
            raise BPSError('API key BPS belum diisi.')
        self.http = httpx.Client(timeout=45, follow_redirects=False, trust_env=False,
                                 transport=transport)
        self.interval, self.last_request = interval, 0.0

    def close(self):
        self.http.close()

    def get(self, path, params=None):
        if not re.fullmatch(r'(?:domain/type/(?:all|prov|kab)|list/model/(?:var|th|data|subject|pressrelease|statictable)/domain/\d{4}(?:/var/\d+/th/\d+)?|view/domain/\d{4}/model/(?:pressrelease|statictable)/lang/(?:ind|eng)/id/\d+)', path):
            raise ValueError('Endpoint di luar cakupan pengambilan BPS.')
        params = params or {}
        if set(params) - {'page', 'var', 'subject', 'lang', 'year', 'month', 'keyword'}:
            raise ValueError('Parameter BPS tidak didukung.')
        time.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        try:
            response = self.http.get('https://webapi.bps.go.id/v1/api/' + path +
                                     '/key/' + quote(self._key, safe=''), params=params)
        except httpx.HTTPError:
            raise BPSError('Koneksi BPS gagal. Progres yang tersimpan dapat dilanjutkan.') from None
        if response.status_code != 200:
            raise BPSError(f'BPS belum menerima permintaan (HTTP {response.status_code}).')
        # Never persist an upstream echo of the secret or a credential-bearing URL.
        if self._key in response.text:
            raise BPSError('Respons BPS memuat kredensial dan tidak disimpan.')
        try:
            data = json.loads(response.text, parse_float=str)
        except ValueError:
            raise BPSError('Respons BPS bukan JSON yang valid.') from None
        if not isinstance(data, dict) or data.get('status') != 'OK':
            raise BPSError('Permintaan BPS ditolak. Periksa API key atau status layanan.')
        return data, response.content

    def pages(self, path, params=None, *, max_pages=1000):
        params = dict(params or {})
        for page in range(1, max_pages + 1):
            data, raw = self.get(path, {**params, 'page': page})
            if data.get('data-availability') == 'not available':
                if page != 1:
                    raise BPSError('Halaman lanjutan BPS tidak tersedia; katalog belum lengkap.')
                yield page, [], raw
                return
            try:
                info, rows = data['data']
                if int(info['page']) != page or not isinstance(rows, list):
                    raise ValueError()
                pages = int(info['pages'])
                if pages < page:
                    raise ValueError()
            except (KeyError, TypeError, ValueError):
                raise BPSError('Struktur halaman BPS berubah; pengambilan dihentikan.') from None
            yield page, rows, raw
            if page == pages:
                return
        raise BPSError('Batas halaman tercapai; katalog tidak dinyatakan lengkap.')
