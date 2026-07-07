import unittest
from unittest.mock import patch

from tech_crawler import main as app_main


class MainTest(unittest.TestCase):
    def test_main_dispatches_to_trending_paper_module(self):
        with patch("tech_crawler.main.pipeline.run_trending_paper_job") as run:
            exit_code = app_main.main(["--module", "trending_paper", "--date", "2026-07-01"])

        self.assertEqual(exit_code, 0)
        run.assert_called_once()
        self.assertEqual(run.call_args.args[1], "2026-07-01")

    def test_main_dispatches_to_today_paper_module(self):
        with patch("tech_crawler.main.pipeline.run_today_paper_job") as run:
            exit_code = app_main.main(["--module", "today_paper", "--date", "2026-07-01"])

        self.assertEqual(exit_code, 0)
        run.assert_called_once()
        self.assertEqual(run.call_args.args[1], "2026-07-01")

    def test_main_rejects_unknown_module(self):
        # argparse raises SystemExit when choices fail. Catching SystemExit or checking return code.
        # Since we use choices, argparse will print usage and exit.
        # However, main handles SystemExit/exceptions if needed, or argparse itself raises it.
        # Let's check how main behaves: exit_code is returned or SystemExit is raised.
        # Actually, parse_args will raise SystemExit(2) directly during args = parse_args(argv).
        with self.assertRaises(SystemExit) as cm:
            app_main.main(["--module", "unknown"])
        self.assertEqual(cm.exception.code, 2)


    def test_main_queries_top_papers(self):
        from tech_crawler.trending_paper.db import PaperRecord
        mock_papers = [
            PaperRecord("url1", "Title 1", "pdf1", "2026-07-07 16:00:00", "2026-07-07 16:13:59", 5)
        ]
        with patch("tech_crawler.main.Path.exists", return_value=True):
            with patch("tech_crawler.main.PaperDatabase") as mock_db_class:
                mock_db = mock_db_class.return_value
                mock_db.get_top_papers.return_value = mock_papers
                
                with patch("tech_crawler.main.pipeline.run_trending_paper_job") as run:
                    exit_code = app_main.main(["--module", "trending_paper", "--top", "5"])
                    
        self.assertEqual(exit_code, 0)
        run.assert_not_called()
        mock_db.get_top_papers.assert_called_once_with("trending_papers", 5)
        mock_db.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
