"""Read the immutable extraction snapshot belonging to an index version."""
from pathlib import PurePosixPath
from ngo_corpus import ROOT,read

def source_pages(config,provider,document_id):
    root=config.get('pages_root') or config.get('source_pages_root') or ''
    if root and (PurePosixPath(root).is_absolute() or '..' in PurePosixPath(root).parts):raise ValueError('invalid_pages_root')
    return read(ROOT/root/provider/document_id/'pages.json',[])
