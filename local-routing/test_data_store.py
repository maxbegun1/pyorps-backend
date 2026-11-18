"""Exercise the on-demand GIS cache using a local HTTP server."""
import functools
import http.server
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import data_store

class CacheTests(unittest.TestCase):
    def test_download_cache_missing_and_path_safety(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as cache:
            src=Path(source); (src/'tiles').mkdir(); (src/'tiles'/'sample.tif').write_bytes(b'example')
            handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=source)
            server=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
            base=f'http://127.0.0.1:{server.server_port}'
            try:
                with patch.object(data_store,'BASE',base), patch.object(data_store,'ROOT',Path(cache)), patch.dict(os.environ,{'PYORPS_ALLOW_LOCAL_HTTP':'1'}):
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
