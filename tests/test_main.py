import unittest
from unittest.mock import patch

from tech_crawler import main as app_main


class MainTest(unittest.TestCase):
    def test_main_dispatches_to_trending_paper_module(self):
        with patch("tech_crawler.main.pipeline.run_trending_paper_job") as run:
            exit_code = app_main.main(["--module", "trending_paper", "--date", "2026-07-01"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(run.call_args.args[1], "2026-07-01")

    def test_main_rejects_unknown_module(self):
        exit_code = app_main.main(["--module", "unknown"])

        self.assertEqual(exit_code, 2)


if __name__ == "__main__":
    unittest.main()
