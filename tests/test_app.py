import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app


class DownloadOptionsTests(unittest.TestCase):
    def test_video_options_use_single_file_without_ffmpeg(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            opts = app.build_download_options("video", "720", temp_dir, None, lambda d: None)

            self.assertEqual(opts["format"], "bestvideo[height<=720][ext=mp4]/best[ext=mp4]")
            self.assertNotIn("merge_output_format", opts)

    def test_video_options_merge_with_ffmpeg_when_available(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            opts = app.build_download_options("video", "480", temp_dir, "/usr/bin/ffmpeg", lambda d: None)

            self.assertEqual(opts["format"], "bestvideo[height<=480]+bestaudio/best/best[ext=mp4]")
            self.assertEqual(opts["merge_output_format"], "mp4")

    def test_download_options_include_browser_headers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            opts = app.build_download_options("video", "720", temp_dir, None, lambda d: None)

            self.assertIn("http_headers", opts)
            self.assertIn("User-Agent", opts["http_headers"])
            self.assertIn("Mozilla/5.0", opts["http_headers"]["User-Agent"])

    def test_audio_options_fallback_without_ffmpeg(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            opts = app.build_download_options("audio", "best", temp_dir, None, lambda d: None)

            self.assertEqual(opts["format"], "bestaudio/best")
            self.assertNotIn("postprocessors", opts)
            self.assertNotIn("ffmpeg_location", opts)


if __name__ == "__main__":
    unittest.main()
