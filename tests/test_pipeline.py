import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tech_crawler.trending_paper import pipeline
from tech_crawler.trending_paper.db import PaperDatabase, PaperRecord
from tech_crawler.trending_paper.download_papers import Paper


class PipelineTest(unittest.TestCase):
    def test_update_paper_registry_inserts_new_paper(self):
        papers = [
            Paper(
                title="New Paper",
                paper_url="https://huggingface.co/papers/2606.23050",
                pdf_url="https://arxiv.org/pdf/2606.23050.pdf",
                arxiv_id="2606.23050",
            )
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = PaperDatabase(db_path)
            try:
                new_papers = pipeline.update_paper_registry(db, "trending_papers", papers, update_time="2026-07-07 16:13:59")
                record = db.get_paper("trending_papers", "https://huggingface.co/papers/2606.23050")
            finally:
                db.close()

            self.assertEqual(len(new_papers), 1)
            self.assertEqual(new_papers[0].title, "New Paper")
            self.assertIsNotNone(record)
            self.assertEqual(record.hotness, 1)
            self.assertEqual(record.created_time, "2026-07-07 16:13:59")
            self.assertEqual(record.update_time, "2026-07-07 16:13:59")

    def test_update_paper_registry_increments_hotness_for_existing_paper(self):
        papers = [
            Paper(
                title="Existing Paper",
                paper_url="https://huggingface.co/papers/2606.23050",
                pdf_url="https://arxiv.org/pdf/2606.23050.pdf",
                arxiv_id="2606.23050",
            )
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = PaperDatabase(db_path)
            try:
                # First run - insert
                pipeline.update_paper_registry(db, "trending_papers", papers, update_time="2026-07-07 16:00:00")
                # Second run - increment
                new_papers = pipeline.update_paper_registry(db, "trending_papers", papers, update_time="2026-07-07 16:13:59")
                record = db.get_paper("trending_papers", "https://huggingface.co/papers/2606.23050")
            finally:
                db.close()

            self.assertEqual(len(new_papers), 0)
            self.assertIsNotNone(record)
            self.assertEqual(record.hotness, 2)
            self.assertEqual(record.created_time, "2026-07-07 16:00:00")
            self.assertEqual(record.update_time, "2026-07-07 16:13:59")

    def test_migrate_legacy_txt_to_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            legacy_dir = root / "data" / "papers" / "trending"
            legacy_dir.mkdir(parents=True)
            legacy_file = legacy_dir / "trending_paper.txt"
            legacy_file.write_text(
                "Existing Paper\thttps://huggingface.co/papers/2606.23050\thttps://arxiv.org/pdf/2606.23050.pdf\t2026-07-07 16:00:00\n",
                encoding="utf-8",
            )

            db_path = root / "test.db"
            db = PaperDatabase(db_path)
            try:
                pipeline.migrate_legacy_txt_to_db(root, db)
                record = db.get_paper("trending_papers", "https://huggingface.co/papers/2606.23050")
            finally:
                db.close()

            self.assertIsNotNone(record)
            self.assertEqual(record.title, "Existing Paper")
            self.assertEqual(record.created_time, "2026-07-07 16:00:00")
            self.assertEqual(record.hotness, 1)
            self.assertFalse(legacy_file.exists())
            self.assertTrue(legacy_file.with_suffix(".txt.bak").exists())

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
            path = pipeline.write_daily_paper_file(Path(tmpdir), papers, update_time="2026-07-07 16:13:59")
            content = path.read_text(encoding="utf-8")

        self.assertEqual(path.name, "paper.txt")
        self.assertEqual(
            content,
            "Readable Paper\thttps://huggingface.co/papers/2606.23050\thttps://arxiv.org/pdf/2606.23050.pdf\t2026-07-07 16:13:59\n",
        )

    def test_run_trending_paper_job_only_runs_trending(self):
        trending_paper = Paper(
            title="Trending Paper",
            paper_url="https://huggingface.co/papers/2606.23050",
            pdf_url="https://arxiv.org/pdf/2606.23050.pdf",
            arxiv_id="2606.23050",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "test.db"

            def download_side_effect(paper, output_dir, **kwargs):
                return Path(output_dir) / f"{paper.title}.pdf"

            with patch.dict("os.environ", {}, clear=True):
                with patch("tech_crawler.trending_paper.pipeline.crawler.fetch_papers", return_value=[trending_paper]) as fetch:
                    with patch("tech_crawler.trending_paper.pipeline.download_papers.download_paper", side_effect=download_side_effect) as download:
                        with patch("tech_crawler.trending_paper.pipeline.read_papers.summarize_pdf") as summarize:
                            # First run: downloads and summarizes
                            result1 = pipeline.run_trending_paper_job(root, "2026-07-01", update_time="2026-07-07 16:13:59", db_path=db_path)
                            # Second run: duplicate detection skips downloads and summarizations, updates hotness
                            result2 = pipeline.run_trending_paper_job(root, "2026-07-01", update_time="2026-07-07 16:15:00", db_path=db_path)

            self.assertEqual(result1.trending_downloaded_count, 1)
            self.assertEqual(result1.trending_summarized_count, 1)
            self.assertEqual(result1.trending_added_count, 1)

            self.assertEqual(result2.trending_downloaded_count, 0)
            self.assertEqual(result2.trending_summarized_count, 0)
            self.assertEqual(result2.trending_added_count, 0)

            # Check DB
            db = PaperDatabase(db_path)
            try:
                record = db.get_paper("trending_papers", "https://huggingface.co/papers/2606.23050")
            finally:
                db.close()

            self.assertIsNotNone(record)
            self.assertEqual(record.hotness, 2)
            self.assertEqual(record.created_time, "2026-07-07 16:13:59")
            self.assertEqual(record.update_time, "2026-07-07 16:15:00")

            self.assertEqual(fetch.call_count, 2)
            self.assertEqual(download.call_count, 1)
            self.assertEqual(summarize.call_count, 1)

    def test_run_today_paper_job_only_runs_today(self):
        daily_paper = Paper(
            title="Daily Paper",
            paper_url="https://huggingface.co/papers/2606.23051",
            pdf_url="https://arxiv.org/pdf/2606.23051.pdf",
            arxiv_id="2606.23051",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "test.db"

            def download_side_effect(paper, output_dir, **kwargs):
                return Path(output_dir) / f"{paper.title}.pdf"

            with patch.dict("os.environ", {}, clear=True):
                with patch("tech_crawler.trending_paper.pipeline.crawler.fetch_papers", return_value=[daily_paper]) as fetch:
                    with patch("tech_crawler.trending_paper.pipeline.download_papers.download_paper", side_effect=download_side_effect) as download:
                        with patch("tech_crawler.trending_paper.pipeline.read_papers.summarize_pdf") as summarize:
                            # First run
                            result1 = pipeline.run_today_paper_job(root, "2026-07-01", update_time="2026-07-07 16:13:59", db_path=db_path)
                            # Second run: skips duplicate downloads/summaries
                            result2 = pipeline.run_today_paper_job(root, "2026-07-01", update_time="2026-07-07 16:15:00", db_path=db_path)

            self.assertEqual(result1.trending_downloaded_count, 0)
            self.assertEqual(result1.downloaded_count, 1)
            self.assertEqual(result1.summarized_count, 1)

            self.assertEqual(result2.downloaded_count, 0)
            self.assertEqual(result2.summarized_count, 0)

            # Check DB
            db = PaperDatabase(db_path)
            try:
                record = db.get_paper("daily_papers", "https://huggingface.co/papers/2606.23051")
            finally:
                db.close()

            self.assertIsNotNone(record)
            self.assertEqual(record.hotness, 2)
            self.assertEqual(record.created_time, "2026-07-07 16:13:59")
            self.assertEqual(record.update_time, "2026-07-07 16:15:00")

            self.assertEqual(fetch.call_count, 2)
            self.assertEqual(download.call_count, 1)
            self.assertEqual(summarize.call_count, 1)


if __name__ == "__main__":
    unittest.main()
