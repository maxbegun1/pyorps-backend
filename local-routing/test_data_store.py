"""Exercise the on-demand GIS cache using a local HTTP server."""
import functools
import hashlib
import http.server
import os
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import data_store

class CacheTests(unittest.TestCase):
    def test_release_archive_extracts_related_files_and_checks_hash(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as cache:
            asset=Path(source)/'tile.zip'
            with zipfile.ZipFile(asset,'w') as z:
                z.writestr('layers/land.tif',b'land')
                z.writestr('layers/wet.tif',b'wet')
            spec={'files':{'layers/land.tif':'tile.zip','layers/wet.tif':'tile.zip'},'assets':{'tile.zip':{'bytes':asset.stat().st_size,'sha256':hashlib.sha256(asset.read_bytes()).hexdigest()}}}
            handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=source)
            server=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                with patch.object(data_store,'BASE',f'http://127.0.0.1:{server.server_port}'),patch.object(data_store,'ROOT',Path(cache)),patch.object(data_store,'MANIFEST',spec),patch.dict(os.environ,{'PYORPS_ALLOW_LOCAL_HTTP':'1'}):
                    self.assertEqual(data_store.get_file('layers/land.tif').read_bytes(),b'land')
                    self.assertEqual((Path(cache)/'layers'/'wet.tif').read_bytes(),b'wet')
                    with self.assertRaises(FileNotFoundError): data_store.get_file('unknown')
                    (Path(cache)/'layers'/'land.tif').unlink()
                    spec['assets']['tile.zip']['sha256']='0'*64
                    with self.assertRaisesRegex(OSError,'checksum'): data_store.get_file('layers/land.tif')
                    self.assertFalse((Path(cache)/'layers'/'land.tif').exists())
            finally:
                server.shutdown();server.server_close();thread.join()

    def test_archive_over_cache_limit_is_rejected(self):
        manifest={'files':{'a.tif':'a.zip'},'assets':{'a.zip':{'bytes':100,'sha256':'0'*64}}}
        with tempfile.TemporaryDirectory() as cache:
            with patch.object(data_store,'BASE','https://example.com'),patch.object(data_store,'ROOT',Path(cache)),patch.object(data_store,'MANIFEST',manifest),patch.object(data_store,'CACHE_LIMIT',199):
                with self.assertRaises(data_store.CacheLimitError): data_store.get_file('a.tif')
    def test_download_cache_missing_and_path_safety(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as cache:
            src=Path(source); (src/'tiles').mkdir(); (src/'tiles'/'sample.tif').write_bytes(b'example')
            handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=source)
            server=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
            base=f'http://127.0.0.1:{server.server_port}'
            try:
                with patch.object(data_store,'BASE',base), patch.object(data_store,'ROOT',Path(cache)), patch.object(data_store,'MANIFEST',None), patch.dict(os.environ,{'PYORPS_ALLOW_LOCAL_HTTP':'1'}):
                    p=data_store.get_file('tiles/sample.tif')
                    self.assertEqual(p.read_bytes(),b'example')
                    (src/'tiles'/'sample.tif').unlink()
                    self.assertEqual(data_store.get_file('tiles/sample.tif').read_bytes(),b'example')
                    with self.assertRaises(ValueError): data_store.get_file('../secret')
                    with self.assertRaises(Exception): data_store.get_file('tiles/missing.tif')
                    self.assertFalse((Path(cache)/'tiles'/'missing.tif').exists())
            finally:
                server.shutdown();server.server_close();thread.join()

if __name__=='__main__': unittest.main()
