import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PaperRecord:
    paper_url: str
    title: str
    pdf_url: str
    created_time: str
    update_time: str
    hotness: int


class PaperDatabase:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS trending_papers (
                    paper_url TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    pdf_url TEXT NOT NULL,
                    created_time TEXT NOT NULL,
                    update_time TEXT NOT NULL,
                    hotness INTEGER DEFAULT 1
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_papers (
                    paper_url TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    pdf_url TEXT NOT NULL,
                    created_time TEXT NOT NULL,
                    update_time TEXT NOT NULL,
                    hotness INTEGER DEFAULT 1
                )
            """)

    def get_paper(self, table_name, paper_url):
        cursor = self.conn.cursor()
        cursor.execute(
            f"SELECT paper_url, title, pdf_url, created_time, update_time, hotness FROM {table_name} WHERE paper_url = ?",
            (paper_url,)
        )
        row = cursor.fetchone()
        if row:
            return PaperRecord(
                paper_url=row["paper_url"],
                title=row["title"],
                pdf_url=row["pdf_url"],
                created_time=row["created_time"],
                update_time=row["update_time"],
                hotness=row["hotness"]
            )
        return None

    def insert_paper(self, table_name, record: PaperRecord):
        with self.conn:
            self.conn.execute(
                f"""
                INSERT INTO {table_name} (paper_url, title, pdf_url, created_time, update_time, hotness)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (record.paper_url, record.title, record.pdf_url, record.created_time, record.update_time, record.hotness)
            )

    def update_paper_hotness(self, table_name, paper_url, update_time):
        with self.conn:
            self.conn.execute(
                f"""
                UPDATE {table_name}
                SET hotness = hotness + 1, update_time = ?
                WHERE paper_url = ?
                """,
                (update_time, paper_url)
            )

    def close(self):
        self.conn.close()
