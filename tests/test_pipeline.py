import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tech_crawler.trending_paper import pipeline
from tech_crawler.trending_paper.download_papers import Paper


class PipelineTest(unittest.TestCase):
    def test_append_new_trending_papers_deduplicates_by_paper_url(self):
        papers = [
            Paper(
                title="Existing Paper",
                paper_url="https://huggingface.co/papers/2606.23050",
                pdf_url="https://arxiv.org/pdf/2606.23050.pdf",
                arxiv_id="2606.23050",
            ),
            Paper(
                title="New Paper",
                paper_url="https://huggingface.co/papers/2606.23051",
                pdf_url="https://arxiv.org/pdf/2606.23051.pdf",
                arxiv_id="2606.23051",
            ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "data" / "papers" / "trending" / "trending_paper.txt"
            index_path.parent.mkdir(parents=True)
            index_path.write_text(
                "Existing Paper\thttps://huggingface.co/papers/2606.23050\thttps://arxiv.org/pdf/2606.23050.pdf\n",
                encoding="utf-8",
            )

            added = pipeline.append_new_trending_papers(index_path, papers)

            lines = index_path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(added, 1)
        self.assertEqual(len(lines), 2)
        self.assertIn("New Paper\thttps://huggingface.co/papers/2606.23051\thttps://arxiv.org/pdf/2606.23051.pdf", lines)

    def test_append_new_trending_papers_reads_legacy_plural_index(self):
        papers = [
            Paper(
                title="Existing Paper",
                paper_url="https://huggingface.co/papers/2606.23050",
                pdf_url="https://arxiv.org/pdf/2606.23050.pdf",
                arxiv_id="2606.23050",
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "data" / "papers" / "trending" / "trending_paper.txt"
            legacy_path = index_path.with_name("trending_papers.txt")
            legacy_path.parent.mkdir(parents=True)
            legacy_path.write_text(
                "Existing Paper\thttps://huggingface.co/papers/2606.23050\thttps://arxiv.org/pdf/2606.23050.pdf\n",
                encoding="utf-8",
            )

            added = pipeline.append_new_trending_papers(index_path, papers)

        self.assertEqual(added, 0)

    def test_write_daily_paper_file_stores_metadata(self):
        papers = [
            Paper(
                title="Readable Paper",
                paper_url="https://huggingface.co/papers/2606.23050",
                pdf_url="https://arxiv.org/pdf/2606.23050.pdf",
                arxiv_id="2606.23050",
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = pipeline.write_daily_paper_file(Path(tmpdir), papers)
            content = path.read_text(encoding="utf-8")

        self.assertEqual(path.name, "paper.txt")
        self.assertEqual(
            content,
            "Readable Paper\thttps://huggingface.co/papers/2606.23050\thttps://arxiv.org/pdf/2606.23050.pdf\n",
        )

    def test_run_trending_paper_job_wires_crawl_download_and_summary(self):
        trending_paper = Paper(
            title="Trending Paper",
            paper_url="https://huggingface.co/papers/2606.23050",
            pdf_url="https://arxiv.org/pdf/2606.23050.pdf",
            arxiv_id="2606.23050",
        )
        daily_paper = Paper(
            title="Daily Paper",
            paper_url="https://huggingface.co/papers/2606.23051",
            pdf_url="https://arxiv.org/pdf/2606.23051.pdf",
            arxiv_id="2606.23051",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            
            def download_side_effect(paper, output_dir, **kwargs):
                return Path(output_dir) / f"{paper.title}.pdf"

            with patch.dict("os.environ", {}, clear=True):
                with patch("tech_crawler.trending_paper.pipeline.crawler.fetch_papers", side_effect=[[trending_paper], [daily_paper]]) as fetch:
                    with patch("tech_crawler.trending_paper.pipeline.download_papers.download_paper", side_effect=download_side_effect) as download:
                        with patch("tech_crawler.trending_paper.pipeline.read_papers.summarize_pdf") as summarize:
                            result = pipeline.run_trending_paper_job(root, "2026-07-01")

            self.assertEqual(result.trending_downloaded_count, 1)
            self.assertEqual(result.trending_summarized_count, 1)
            self.assertEqual(result.downloaded_count, 1)
            self.assertEqual(result.summarized_count, 1)
            self.assertEqual(
                (root / "data" / "papers" / "trending" / "trending_paper.txt").read_text(encoding="utf-8"),
                "Trending Paper\thttps://huggingface.co/papers/2606.23050\thttps://arxiv.org/pdf/2606.23050.pdf\n",
            )
            self.assertTrue((root / "data" / "papers" / "20260701" / "paper.txt").exists())
            self.assertEqual(fetch.call_count, 2)
            self.assertEqual(download.call_count, 2)
            self.assertEqual(summarize.call_count, 2)

            expected_trending_pdf = root / "data" / "papers" / "trending" / "Trending Paper.pdf"
            expected_daily_pdf = root / "data" / "papers" / "20260701" / "Daily Paper.pdf"
            summarize.assert_any_call(expected_trending_pdf, delay_seconds=5, proxies={"http": None, "https": None})
            summarize.assert_any_call(expected_daily_pdf, delay_seconds=5, proxies={"http": None, "https": None})


if __name__ == "__main__":
    unittest.main()
