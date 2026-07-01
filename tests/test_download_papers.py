import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tech_crawler.trending_paper import download_papers


class DownloadPapersTest(unittest.TestCase):
    def test_safe_filename_uses_paper_title(self):
        filename = download_papers.safe_paper_filename(
            'A/B: Better* Paper? "Now" <Test> | Demo',
            extension=".pdf",
        )

        self.assertEqual(filename, "A B Better Paper Now Test Demo.pdf")

    def test_safe_filename_limits_length(self):
        filename = download_papers.safe_paper_filename("a" * 220, extension=".pdf")

        self.assertEqual(filename, f"{'a' * 180}.pdf")

    def test_unique_output_path_uses_arxiv_id_for_title_collision(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            (output_dir / "Paper Title.pdf").write_text("existing", encoding="utf-8")

            path = download_papers.unique_output_path(
                output_dir,
                title="Paper Title",
                arxiv_id="2606.23050",
                extension=".pdf",
            )

        self.assertEqual(path.name, "Paper Title - 2606.23050.pdf")

    def test_daily_output_dir_uses_yyyymmdd_under_data_papers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertEqual(
                download_papers.daily_output_dir(Path(tmpdir), "2026-07-01"),
                Path(tmpdir) / "data" / "papers" / "20260701",
            )

    def test_trending_output_dir_uses_trending_under_data_papers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertEqual(
                download_papers.trending_output_dir(Path(tmpdir)),
                Path(tmpdir) / "data" / "papers" / "trending",
            )

    def test_proxy_config_respects_use_proxy_switch(self):
        env = {
            "USE_PROXY": "1",
            "http_proxy": "http://127.0.0.1:7890",
            "https_proxy": "http://127.0.0.1:7891",
        }

        with patch.dict("os.environ", env, clear=True):
            proxies = download_papers.load_proxy_config()

        self.assertEqual(
            proxies,
            {
                "http": "http://127.0.0.1:7890",
                "https": "http://127.0.0.1:7891",
            },
        )

    def test_proxy_config_disabled_when_use_proxy_is_zero(self):
        env = {
            "USE_PROXY": "0",
            "http_proxy": "http://127.0.0.1:7890",
            "https_proxy": "http://127.0.0.1:7891",
        }

        with patch.dict("os.environ", env, clear=True):
            proxies = download_papers.load_proxy_config()

        self.assertEqual(proxies, {"http": None, "https": None})

    def test_download_paper_uses_title_filename_proxy_and_delay(self):
        paper = download_papers.Paper(
            title="Readable Paper Title",
            paper_url="https://huggingface.co/papers/2606.23050",
            pdf_url="https://arxiv.org/pdf/2606.23050.pdf",
            arxiv_id="2606.23050",
        )
        response = Mock()
        response.iter_content.return_value = [b"pdf"]
        response.raise_for_status.return_value = None

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            with patch("tech_crawler.trending_paper.download_papers.requests.get", return_value=response) as get:
                with patch("tech_crawler.trending_paper.download_papers.time.sleep") as sleep:
                    path = download_papers.download_paper(
                        paper,
                        output_dir,
                        proxies={"https": "http://proxy"},
                        delay_seconds=20,
                    )

            self.assertEqual(path, output_dir / "Readable Paper Title.pdf")
            self.assertEqual(path.read_bytes(), b"pdf")
            get.assert_called_once()
            self.assertEqual(get.call_args.kwargs["proxies"], {"https": "http://proxy"})
            sleep.assert_called_once_with(20)

    def test_download_paper_retries_transient_request_error(self):
        paper = download_papers.Paper(
            title="Readable Paper Title",
            paper_url="https://huggingface.co/papers/2606.23050",
            pdf_url="https://arxiv.org/pdf/2606.23050.pdf",
            arxiv_id="2606.23050",
        )
        response = Mock()
        response.iter_content.return_value = [b"pdf"]
        response.raise_for_status.return_value = None

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            with patch(
                "tech_crawler.trending_paper.download_papers.requests.get",
                side_effect=[download_papers.requests.exceptions.SSLError("tls eof"), response],
            ) as get:
                with patch("tech_crawler.trending_paper.download_papers.time.sleep") as sleep:
                    path = download_papers.download_paper(
                        paper,
                        output_dir,
                        delay_seconds=20,
                        max_attempts=2,
                        retry_delay_seconds=7,
                    )

            self.assertEqual(path.read_bytes(), b"pdf")
            self.assertEqual(get.call_count, 2)
            sleep.assert_any_call(7)
            sleep.assert_any_call(20)

    def test_download_paper_skips_existing_pdf_without_sleep(self):
        paper = download_papers.Paper(
            title="Readable Paper Title",
            paper_url="https://huggingface.co/papers/2606.23050",
            pdf_url="https://arxiv.org/pdf/2606.23050.pdf",
            arxiv_id="2606.23050",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            existing = output_dir / "Readable Paper Title.pdf"
            existing.write_text("existing", encoding="utf-8")
            with patch("tech_crawler.trending_paper.download_papers.requests.get") as get:
                with patch("tech_crawler.trending_paper.download_papers.time.sleep") as sleep:
                    path = download_papers.download_paper(paper, output_dir)

        self.assertEqual(path, existing)
        get.assert_not_called()
        sleep.assert_not_called()

    def test_download_paper_does_not_skip_if_existing_pdf_is_empty(self):
        paper = download_papers.Paper(
            title="Readable Paper Title",
            paper_url="https://huggingface.co/papers/2606.23050",
            pdf_url="https://arxiv.org/pdf/2606.23050.pdf",
            arxiv_id="2606.23050",
        )
        response = Mock()
        response.iter_content.return_value = [b"pdf"]
        response.raise_for_status.return_value = None

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            existing = output_dir / "Readable Paper Title.pdf"
            existing.write_text("", encoding="utf-8") # Empty file
            with patch("tech_crawler.trending_paper.download_papers.requests.get", return_value=response) as get:
                with patch("tech_crawler.trending_paper.download_papers.time.sleep") as sleep:
                     path = download_papers.download_paper(paper, output_dir, delay_seconds=0)

            self.assertEqual(path, existing)
            self.assertEqual(path.read_bytes(), b"pdf")
            get.assert_called_once()
            sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
