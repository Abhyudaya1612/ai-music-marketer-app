"""Seed the database with 3 demo songs and run the full agent pipeline.

Usage (from repo root):
    python -m scripts.seed
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal, init_db
from backend.models import Song
from backend.workers import execute_pipeline

NL = chr(10)

DEMO_SONGS = [
    dict(title="Neon Skyline", artist="The Midnight Runners", genre="indie electronic",
         lyrics=NL.join(["Neon skyline in the rearview mirror",
                         "Every light in this city's getting clearer",
                         "We were born to outrun the night",
                         "City lights, city lights",
                         "Driving till the morning takes us higher",
                         "Neon skyline burning like a fire",
                         "We were born to outrun the night",
                         "City lights, city lights"])),
    dict(title="Golden Hour Grind", artist="Kayla Voss", genre="pop",
         lyrics=NL.join(["Wake up, chase the golden hour",
                         "Built an empire, feels like power",
                         "We were born to win the fight",
                         "Top of the world tonight",
                         "Money on my mind but love in my heart",
                         "We were born to win the fight",
                         "Top of the world tonight"])),
    dict(title="Rainy Window", artist="Aldo Ferreira", genre="lo-fi",
         lyrics=NL.join(["Rainy window, coffee cold",
                         "Stories of the days of old",
                         "Empty room, I miss you so",
                         "Watching all the shadows fade",
                         "Empty room, I miss you so",
                         "Watching all the shadows fade"])),
]


def main():
    init_db()
    db = SessionLocal()
    try:
        for data in DEMO_SONGS:
            if db.query(Song).filter_by(title=data["title"], artist=data["artist"]).first():
                continue
            song = Song(**data)
            db.add(song)
            db.commit()
            db.refresh(song)
            run_id = execute_pipeline(song.id, db)
            print(f"OK '{song.title}' analyzed (run #{run_id}, status={song.status})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
