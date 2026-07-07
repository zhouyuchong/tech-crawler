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


if __name__ == "__main__":
    unittest.main()
