from pathlib import Path

from dotenv import load_dotenv

from .database import initialize_database, make_engine


def main():
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    engine = make_engine()
    try:
        initialize_database(engine)
        print('DATABASE_INIT_OK')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
