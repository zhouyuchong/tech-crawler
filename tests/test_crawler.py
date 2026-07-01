import unittest
from unittest.mock import Mock, patch

from tech_crawler.trending_paper import crawler


class CrawlerTest(unittest.TestCase):
    def test_daily_url_uses_requested_date(self):
        self.assertEqual(
            crawler.daily_paper_url("https://huggingface.co/papers/date/2026-01-01", "2026-07-01"),
            "https://huggingface.co/papers/date/2026-07-01",
        )

    def test_parse_papers_extracts_title_paper_url_and_pdf_url(self):
        html = """
        <html>
          <body>
            <h3><a href="/papers/2606.23050">Readable Paper Title</a></h3>
            <h3><a href="/papers/2606.23051">Second Paper</a></h3>
          </body>
        </html>
        """

        papers = crawler.parse_papers(html)

        self.assertEqual(len(papers), 2)
        self.assertEqual(papers[0].title, "Readable Paper Title")
        self.assertEqual(papers[0].paper_url, "https://huggingface.co/papers/2606.23050")
        self.assertEqual(papers[0].pdf_url, "https://arxiv.org/pdf/2606.23050.pdf")
        self.assertEqual(papers[0].arxiv_id, "2606.23050")

    def test_fetch_papers_uses_proxy_and_delay(self):
        response = Mock()
        response.text = '<h3><a href="/papers/2606.23050">Readable Paper Title</a></h3>'
        response.raise_for_status.return_value = None

        with patch("tech_crawler.trending_paper.crawler.requests.get", return_value=response) as get:
            with patch("tech_crawler.trending_paper.crawler.time.sleep") as sleep:
                papers = crawler.fetch_papers(
                    "https://huggingface.co/papers/trending",
                    proxies={"https": "http://proxy"},
                    delay_seconds=10,
                )

        self.assertEqual(len(papers), 1)
        self.assertEqual(get.call_args.kwargs["proxies"], {"https": "http://proxy"})
        sleep.assert_called_once_with(10)


if __name__ == "__main__":
    unittest.main()
