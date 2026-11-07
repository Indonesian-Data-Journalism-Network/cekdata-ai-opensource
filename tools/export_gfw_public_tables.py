"""Export public regional CSVs so saved answers need no GFW API access."""
import csv
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'workflow'))
from gfw_sources import public_evidence, IDENTITY

def main():
    archive=ROOT/'data/gfw-adm2/records.jsonl'
    if not archive.exists(): archive=ROOT/'data/gfw/records.jsonl'
    directory=ROOT/'web/frontend/public/gfw-evidence'
    directory.mkdir(parents=True,exist_ok=True)
    fields=['area','year','indicator','value','unit','source','source_url','api_source_url',
            'download_url','methodology_url','source_record_id','dataset_version','canopy_threshold']
    groups={}
    with archive.open() as source:
        for line in source:
            row=public_evidence(json.loads(line))
            match=IDENTITY.fullmatch(row['source_record_id'])
            level,_,code,_,_=match.groups()
            slug='iso-IDN' if level=='iso' else level+'-'+code.replace('.','-')
            groups.setdefault(slug,[]).append(row)
    for slug,rows in groups.items():
        path=directory/(slug+'.csv')
        temporary=path.with_suffix('.tmp')
        with temporary.open('w',encoding='utf-8-sig',newline='') as target:
            writer=csv.DictWriter(target,fieldnames=fields,extrasaction='ignore')
            writer.writeheader();writer.writerows(sorted(rows,key=lambda r:(r['year'],r['indicator'])))
        temporary.replace(path)
    print(len(groups),'public regional CSV files;',sum(map(len,groups.values())),'observations')

if __name__=='__main__':main()
