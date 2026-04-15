"""Standalone FTP sync worker process for Docker deployment."""
import logging
import time

from app import app
from models import Settings
from utils.ftp_sync import sync_printer_files

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def main():
    logger.info("FTP sync worker started")

    while True:
        with app.app_context():
            settings = Settings.query.first()
            if settings and settings.ftp_sync_enabled and settings.ftp_host:
                try:
                    result = sync_printer_files(app)
                    if result.get('new_files', 0) > 0:
                        logger.info(f"Sync: {result['new_files']} neue Dateien")
                    else:
                        logger.debug(f"Sync: keine neuen Dateien")
                except Exception as e:
                    logger.error(f"Sync error: {e}")

        time.sleep(300)


if __name__ == '__main__':
    main()
