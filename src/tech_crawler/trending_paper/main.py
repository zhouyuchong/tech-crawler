"""Compatibility entrypoint for the trending paper job."""

from tech_crawler.main import main


if __name__ == "__main__":
    raise SystemExit(main(["--module", "trending_paper"]))
