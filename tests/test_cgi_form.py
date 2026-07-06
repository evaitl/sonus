from __future__ import annotations

import io
import os
import sys
import unittest
from unittest import mock

from sonus.cgi.form import CgiForm, UploadedFile, read_cgi_form


class CgiFormTests(unittest.TestCase):
    def test_getfirst_returns_first_value_and_default(self) -> None:
        form = CgiForm({"title": ["Hello", "World"], "artist": [""]})
        self.assertEqual(form.getfirst("title"), "Hello")
        self.assertIsNone(form.getfirst("missing"))
        self.assertEqual(form.getfirst("missing", ""), "")
        self.assertEqual(form.getfirst("artist"), "")

    def test_getlist(self) -> None:
        form = CgiForm({"tag": ["a", "b"]})
        self.assertEqual(form.getlist("tag"), ["a", "b"])
        self.assertEqual(form.getlist("missing"), [])

    def test_getfile(self) -> None:
        upload = UploadedFile(
            filename="cover.png",
            content_type="image/png",
            value=b"png-bytes",
        )
        form = CgiForm({}, {"art": [upload]})
        self.assertEqual(form.getfile("art"), upload)
        self.assertEqual(form.getfilelist("art"), [upload])
        self.assertIsNone(form.getfile("missing"))

    def test_read_cgi_form_get(self) -> None:
        env = {
            "REQUEST_METHOD": "GET",
            "QUERY_STRING": "title=Blue+Moon&artist=Sinatra&page=2",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            form = read_cgi_form()
        self.assertEqual(form.getfirst("title"), "Blue Moon")
        self.assertEqual(form.getfirst("artist"), "Sinatra")
        self.assertEqual(form.getfirst("page"), "2")

    def test_read_cgi_form_post_urlencoded(self) -> None:
        body = "username=ada&password=secret&next=index.py"
        env = {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": "application/x-www-form-urlencoded",
            "CONTENT_LENGTH": str(len(body)),
        }
        stdin = io.StringIO(body)
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(sys, "stdin", stdin):
                form = read_cgi_form()
        self.assertEqual(form.getfirst("username"), "ada")
        self.assertEqual(form.getfirst("password"), "secret")
        self.assertEqual(form.getfirst("next"), "index.py")

    def test_read_cgi_form_post_multipart(self) -> None:
        body = (
            b"--abc\r\n"
            b'Content-Disposition: form-data; name="id"\r\n\r\n'
            b"42\r\n"
            b"--abc\r\n"
            b'Content-Disposition: form-data; name="art"; filename="cover.png"\r\n'
            b"Content-Type: image/png\r\n\r\n"
            b"\x89PNG\r\n\x1a\npayload\r\n"
            b"--abc--\r\n"
        )
        env = {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": "multipart/form-data; boundary=abc",
            "CONTENT_LENGTH": str(len(body)),
        }
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(sys, "stdin", io.TextIOWrapper(io.BytesIO(body))):
                form = read_cgi_form()
        self.assertEqual(form.getfirst("id"), "42")
        upload = form.getfile("art")
        assert upload is not None
        self.assertEqual(upload.filename, "cover.png")
        self.assertEqual(upload.content_type, "image/png")
        self.assertTrue(upload.value.startswith(b"\x89PNG"))

    def test_cgi_scripts_do_not_import_stdlib_cgi(self) -> None:
        root = os.path.join(os.path.dirname(__file__), "..", "web", "cgi-bin")
        for name in os.listdir(root):
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            with open(path, encoding="utf-8") as handle:
                source = handle.read()
            self.assertNotIn("import cgi", source, path)
            self.assertNotIn("from cgi", source, path)


if __name__ == "__main__":
    unittest.main()
