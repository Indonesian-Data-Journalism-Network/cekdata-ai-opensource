"""Archive BRS titles and abstract text only. Never request PDF/slide URLs.

Release year is discovery metadata, not the observation year of every number.
Text is staged separately from statistical cells and is not auto-published.
"""
import argparse
from datetime import date
from html.parser import HTMLParser
import hashlib
import json
import os
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit

from tools.bps.client import BPSClient, BPSError
from tools.bps.ingest import Archive, DEFAULT_DIR, ROOT, now, write_json


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self.hidden += 1
        if tag in {'p','br','li','tr','div'}:
            self.parts.append('\n')
        elif tag in {'td','th'}:
            self.parts.append(' | ')

    def handle_endtag(self, tag):
        if tag in {'script','style'}:
            self.hidden = max(0, self.hidden - 1)
        if tag in {'p','li','tr','div'}:
            self.parts.append('\n')

    def handle_data(self, text):
        if not self.hidden:
            self.parts.append(text)


def plain_text(value):
    p = TextParser()
    p.feed(value or '')
    return '\n'.join(line for line in
                     (re.sub(r'\s+', ' ', x).strip() for x in ''.join(p.parts).splitlines()) if line)


def safe_download_url(value):
    if not isinstance(value, str) or not value:
        return ''
    u = urlsplit(value)
    if (u.scheme != 'https' or not (u.hostname == 'bps.go.id' or (u.hostname or '').endswith('.bps.go.id'))
            or u.username or u.password or '/key/' in value or 'api_key' in value.casefold()):
        return ''
    return value


def record(detail, saved, domain, publisher_url, release_year):
    if detail.get('status') != 'OK' or detail.get('data-availability') != 'available':
        raise BPSError('Detail BRS tidak tersedia; koleksi belum dinyatakan lengkap.')
    body = detail.get('data')
    if not isinstance(body, dict) or not str(body.get('brs_id','')).isdigit():
        raise BPSError('Identitas BRS tidak valid.')
    title, text = plain_text(body.get('title')), plain_text(body.get('abstract'))
    if not title:
        raise BPSError('Judul BRS kosong.')
    released = date.fromisoformat(str(body.get('rl_date',''))[:10])
    if released.year != release_year:
        raise BPSError('Tahun rilis tidak cocok dengan filter pengambilan.')
    host = urlsplit(publisher_url)
    if host.scheme != 'https' or not (host.hostname == 'bps.go.id' or (host.hostname or '').endswith('.bps.go.id')):
        raise BPSError('Domain halaman publik BPS tidak valid.')
    slug = re.sub(r'[^a-z0-9]+', '-', unicodedata.normalize('NFKD', title).encode('ascii','ignore').decode().lower()).strip('-')
    return {'id': f'bps-brs-{domain}-{body["brs_id"]}', 'source_type': 'bps_pressrelease',
            'publisher': 'Badan Pusat Statistik', 'publisher_domain_id': domain,
            'release_id': str(body['brs_id']), 'title': title, 'text': text,
            'search_text': title + '\n\n' + text,
            'release_date': released.isoformat(), 'release_year': release_year,
            'updated_at': body.get('updt_date'), 'retrieved_at': saved['retrieved_at'],
            'observation_periods': [], 'geographic_scope': [],
            'period_scope_status': 'requires_extraction_from_title_and_text',
            'source_url': publisher_url.rstrip('/') + f'/id/pressrelease/{released:%Y/%m/%d}/{body["brs_id"]}/{slug}.html',
            'source_url_origin': 'constructed_from_official_release_metadata',
            'source_url_verified': False,
            'download_url': safe_download_url(body.get('pdf')),
            'download_file_fetched': False,
            'text_coverage': 'api_title_and_abstract_only',
            'text_status': 'available' if text else 'empty_abstract',
            'source_snapshot_sha256': saved['sha256'],
            'text_sha256': hashlib.sha256((title+'\n\n'+text).encode()).hexdigest(),
            'subject': body.get('subj') or body.get('subcsa'),
            'ready_for_numeric_answers': False}


def collect(archive, year, domain='0000', publisher_url='https://www.bps.go.id'):
    path = archive.root / f'brs-{domain}-{year}-manifest.json'
    rows, _ = archive.list(f'list/model/pressrelease/domain/{domain}', {'year':year,'lang':'ind'})
    ids = [str(r['brs_id']) for r in rows]
    if len(set(ids)) != len(ids):
        raise BPSError('ID BRS berulang pada katalog.')
    documents = []
    for i, ident in enumerate(ids, 1):
        data, saved = archive.get(f'view/domain/{domain}/model/pressrelease/lang/ind/id/{ident}')
        doc = record(data, saved, domain, publisher_url, year)
        if doc['release_id'] != ident:
            raise BPSError('Identitas respons BRS berbeda dari permintaan.')
        write_json(archive.root/'documents'/(doc['id']+'.json'),doc)
        documents.append(doc)
        if i == 1 or i % 10 == 0 or i == len(ids):
            print(json.dumps({'completed':i,'total':len(ids),'pdf_downloads':0}),flush=True)
    manifest = {'status':'text_archived','release_year':year,'publisher_domain_id':domain,
                'documents':len(documents),'with_abstract':sum(bool(d['text']) for d in documents),
                'with_pdf_link':sum(bool(d['download_url']) for d in documents),
                'pdf_downloads':0,'qdrant_ingested':False,'completed_at':now(),
                'document_ids':[d['id'] for d in documents],
                'observation_year_not_inferred_from_release_year':True,
                'public_page_links_require_verification':True}
    write_json(path,manifest)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--year',type=int,required=True)
    parser.add_argument('--directory',type=Path,default=DEFAULT_DIR/'brs')
    parser.add_argument('--refresh',action='store_true')
    args=parser.parse_args()
    key=os.environ.get('BPS_API_KEY') or json.loads((ROOT/'.local/bps-connection.json').read_text()).get('api_key','')
    client=BPSClient(key)
    try:
        archive=Archive(args.directory,client,refresh=args.refresh,max_requests=250)
        print(json.dumps(collect(archive,args.year),ensure_ascii=False),flush=True)
    except (BPSError,ValueError) as exc:
        parser.exit(2,str(exc)+'\n')
    finally:
        client.close()


if __name__=='__main__':main()
