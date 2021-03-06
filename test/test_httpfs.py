import os
import logging
import threading
from unittest import TestCase
from stat import S_IFDIR, S_IFREG
from http.server import HTTPServer
from http.server import SimpleHTTPRequestHandler

import httpfs


def get_fs_path(p):
    path = os.path.join(os.path.dirname(__file__),
                        "testwww", os.path.relpath(p))
    logging.info("get_fs_path: translated path %s -> %s", p, path)
    return path


class Handler(SimpleHTTPRequestHandler):

    def translate_path(self, path):
        path_new = get_fs_path(super().translate_path(path))
        logging.info("translated %s to %s", path, path_new)
        return path_new

    def handle_one_request(self, *a):
        SimpleHTTPRequestHandler.handle_one_request(self, *a)
        self.server.requests.append(vars(self))


class TestBase(TestCase):

    def setUp(self):
        self.server = HTTPServer(('', 0), Handler)
        self.server.requests = []
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()

        httpfs.Config.verify = "default"
        self.httpfs = httpfs.Httpfs()
        self.port = self.server.socket.getsockname()[1]

    def tearDown(self):
        self.server.shutdown()
        self.server_thread.join()

    def basePath(self):
        return "/http/localhost:{}".format(self.port)

    def stat(self, path):
        return os.stat(get_fs_path(path))


class TestZwei(TestBase):

    def test_root(self):
        r = self.httpfs.readdir(self.basePath(), None)
        self.assertEqual(len(self.server.requests), 2)  # made 2 requests
        self.assertEqual(self.server.requests[0]["command"], "GET")
        self.assertEqual(self.server.requests[1]["command"], "HEAD")

        files = dict(map(lambda i: (i[0], i[1]), r))
        self.assertSetEqual(set(('bla', 'dir', '..', '.')), set(files.keys()))
        self.assertEqual(files['.']['st_mode'], S_IFDIR | 0o555)
        self.assertEqual(files['.']['st_nlink'], self.stat(".").st_nlink)
        self.assertEqual(files['..']['st_mode'], S_IFDIR | 0o555)
        self.assertEqual(files['bla']['st_mode'], S_IFREG | 0o444)
        self.assertEqual(files['dir']['st_mode'], S_IFDIR | 0o555)

    def test_dir(self):
        r = self.httpfs.readdir(self.basePath() + "/", None)
        self.assertEqual(len(r), 4)

        r = self.httpfs.readdir(self.basePath() + "/dir", None)
        self.assertEqual(len(r), 5)

    def test_subdir(self):
        r = self.httpfs.readdir(self.basePath() + "/dir/subdir", None)
        self.assertEqual(len(r), 3)

    def test_dir_ending_slash(self):
        r = self.httpfs.readdir(self.basePath() + "/dir/", None)
        self.assertEqual(len(r), 5)

    def test_read(self):
        expected = open(get_fs_path("dir/bla1"), "rb").read()
        result = self.httpfs.read(self.basePath() + "/dir/bla1", 1000, 0, None)
        self.assertEqual(expected, result)
