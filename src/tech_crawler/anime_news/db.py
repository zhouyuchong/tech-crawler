import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AnimeNewsRecord:
    guid: str
    title: str
    link: str
    description: str
    pub_date: str
    created_time: str


class AnimeNewsDatabase:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS anime_news (
                    guid TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    link TEXT NOT NULL,
                    description TEXT,
                    pub_date TEXT,
                    created_time TEXT NOT NULL
                )
            """)

    def get_news(self, guid):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT guid, title, link, description, pub_date, created_time FROM anime_news WHERE guid = ?",
            (guid,)
        )
        row = cursor.fetchone()
        if row:
            return AnimeNewsRecord(
                guid=row["guid"],
                title=row["title"],
                link=row["link"],
                description=row["description"],
                pub_date=row["pub_date"],
                created_time=row["created_time"],
            )
        return None

    def insert_news(self, record: AnimeNewsRecord):
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO anime_news (guid, title, link, description, pub_date, created_time)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (record.guid, record.title, record.link, record.description, record.pub_date, record.created_time)
            )

    def close(self):
        self.conn.close()
