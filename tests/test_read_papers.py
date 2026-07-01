import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tech_crawler.trending_paper import read_papers


class ReadPapersTest(unittest.TestCase):
    def test_build_prompt_requests_summary_and_innovation(self):
        prompt = read_papers.build_prompt("Readable Paper.pdf", "paper text")

        self.assertIn("Readable Paper.pdf", prompt)
        self.assertIn("总结", prompt)
        self.assertIn("创新点", prompt)
        self.assertIn("是什么", prompt)
        self.assertIn("为什么重要", prompt)
        self.assertIn("与已有方法差异", prompt)
        self.assertIn("证据或效果", prompt)
        self.assertIn("paper text", prompt)

    def test_call_llm_uses_openai_compatible_chat_completions_and_proxy(self):
        response = Mock()
        response.json.return_value = {
            "choices": [{"message": {"content": "## 总结\n...\n## 创新点\n..."}}]
        }
        response.raise_for_status.return_value = None

        with patch("tech_crawler.trending_paper.read_papers.requests.post", return_value=response) as post:
            result = read_papers.call_llm(
                prompt="请总结",
                api_key="test-key",
                base_url="https://example.com/v1",
                model="test-model",
                proxies={"https": "http://proxy"},
            )

        self.assertEqual(result, "## 总结\n...\n## 创新点\n...")
        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], "https://example.com/v1/chat/completions")
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(post.call_args.kwargs["json"]["model"], "test-model")
        self.assertEqual(post.call_args.kwargs["json"]["messages"][-1]["content"], "请总结")
        self.assertEqual(post.call_args.kwargs["proxies"], {"https": "http://proxy"})

    def test_load_llm_config_prefers_project_env_names(self):
        env = {
            "DEEPSEEK_API_KEY": "deepseek-key",
            "BASE_URL": "https://deepseek.example/v1",
            "BASE_MODEL": "deepseek-chat",
            "OPENAI_API_KEY": "openai-key",
            "OPENAI_BASE_URL": "https://openai.example/v1",
            "OPENAI_MODEL": "gpt-test",
        }

        with patch.dict("os.environ", env, clear=True):
            config = read_papers.load_llm_config()

        self.assertEqual(config.api_key, "deepseek-key")
        self.assertEqual(config.base_url, "https://deepseek.example/v1")
        self.assertEqual(config.model, "deepseek-chat")

    def test_summarize_pdf_writes_markdown_next_to_pdf_and_sleeps(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "Readable Paper.pdf"
            pdf_path.write_bytes(b"%PDF")
            with patch("tech_crawler.trending_paper.read_papers.extract_pdf_text", return_value="paper text"):
                with patch("tech_crawler.trending_paper.read_papers.call_llm", return_value="summary"):
                    with patch("tech_crawler.trending_paper.read_papers.time.sleep") as sleep:
                        output = read_papers.summarize_pdf(
                            pdf_path,
                            api_key="key",
                            base_url="https://example.com/v1",
                            model="model",
                            delay_seconds=5,
                        )

            self.assertEqual(output, Path(tmpdir) / "Readable Paper.md")
            self.assertEqual(output.read_text(encoding="utf-8"), "summary\n")
            sleep.assert_called_once_with(5)

    def test_summarize_pdf_skips_existing_markdown_without_calling_llm(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "Readable Paper.pdf"
            pdf_path.write_bytes(b"%PDF")
            markdown_path = Path(tmpdir) / "Readable Paper.md"
            markdown_path.write_text("existing", encoding="utf-8")

            with patch("tech_crawler.trending_paper.read_papers.call_llm") as call_llm:
                with patch("tech_crawler.trending_paper.read_papers.time.sleep") as sleep:
                    output = read_papers.summarize_pdf(
                        pdf_path,
                        api_key="key",
                        base_url="https://example.com/v1",
                        model="model",
                    )

        self.assertEqual(output, markdown_path)
        call_llm.assert_not_called()
        sleep.assert_not_called()

    def test_summarize_pdf_does_not_skip_if_existing_markdown_is_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "Readable Paper.pdf"
            pdf_path.write_bytes(b"%PDF")
            markdown_path = Path(tmpdir) / "Readable Paper.md"
            markdown_path.write_text("", encoding="utf-8") # Empty file

            with patch("tech_crawler.trending_paper.read_papers.extract_pdf_text", return_value="paper text"):
                with patch("tech_crawler.trending_paper.read_papers.call_llm", return_value="new summary") as call_llm:
                    with patch("tech_crawler.trending_paper.read_papers.time.sleep") as sleep:
                        output = read_papers.summarize_pdf(
                            pdf_path,
                            api_key="key",
                            base_url="https://example.com/v1",
                            model="model",
                            delay_seconds=0,
                        )

            self.assertEqual(output, markdown_path)
            self.assertEqual(output.read_text(encoding="utf-8"), "new summary\n")
            call_llm.assert_called_once()
            sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
