import getpass
import logging
import os
import socket
import sys
from contextlib import suppress
from datetime import datetime
from logging.handlers import RotatingFileHandler
from urllib.parse import urljoin

import requests


class CustomRotatingFileHandler(RotatingFileHandler):
    def __init__(
        self, filename, mode="a", maxBytes=0, encoding=None, delay=False
    ):
        self.last_backup_cnt = 0
        super().__init__(
            filename=filename,
            mode=mode,
            maxBytes=maxBytes,
            backupCount=0,
            encoding=encoding,
            delay=delay,
        )

    # override
    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        # my code starts here
        self.last_backup_cnt += 1
        nextName = "%s.%d" % (self.baseFilename, self.last_backup_cnt)
        self.rotate(self.baseFilename, nextName)
        # my code ends here
        if not self.delay:
            self.stream = self._open()


class LogServerHandler(logging.StreamHandler):
    def __init__(self, server=None, source=None):
        if server is None:
            with open("/operations/app_store/python_diag/logging_server.txt", "r") as f:
                server = f.readline().strip()

        self._entered = False
        self.server = server
        self.source = source or sys.argv[0] or "Unknown Python application"
        super().__init__()

    def emit(self, record: logging.LogRecord):
        if self._entered:
            return

        self._entered = True
        try:
            url = urljoin(self.server, "/api/entries/")
            msg = self.format(record)
            data = {
                "host": socket.gethostname(),
                "level": record.levelname,
                "contents": msg,
                "source": self.source,
                "user": getpass.getuser(),
                "timestamp": record.created,
            }

            with suppress(Exception):
                requests.post(url, json=data)
        finally:
            self._entered = False


def enable_exception_handler():
    import logging

    def logging_handler(exctype, value, tb):
        if exctype is KeyboardInterrupt:
            exit(0)

        logging.exception("Uncaught exception", exc_info=value)
        sys.__excepthook__(exctype, value, tb)

    # Install exception handler
    sys.excepthook = logging_handler


def enable_logging(
    enable_fs=True,
    fs_path=None,
    fs_level=logging.INFO,
    enable_db=True,
    db_level=logging.INFO,
    console_level=None,
):
    """Enables the default C-AD logging configuration for Python programs
    Defaults to database logging, filesystem logging optional

    Args:
        enable_fs (bool, optional): Enables logging to filesystem text file. Defaults to False.
        fs_path (str, optional): Path to log file used if enable_fs=True. Defaults to /operations/app_store/<program>/diagnostics/message.
        fs_level (int, optional): Log level to use for filesystem handler. Defaults to INFO.
        enable_db (bool, optional): Enables logging to database server. Defaults to True.
        db_level (int, optional): Log level to use for database handler. Defaults to INFO.
        console_level (int, optional): Log level to use for console handler. Defaults to WARNING.
    """
    script_name = os.path.basename(sys.argv[0])
    if script_name == "__main__.py":
        import pathlib

        path = pathlib.Path(sys.argv[0])
        script_name = path.parts[-2]

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(pathname)s:%(lineno)s - %(message)s", style="%"
    )
    if enable_fs:
        if not fs_path:
            hostname = socket.gethostname().replace(".pbn.bnl.gov", "")
            logging_dir = f"/operations/app_store/{script_name}/diagnostics/message"
            ts = datetime.now().strftime("%Y-%m%d_%H:%M:%S")
            logging_file = f"{ts}_{hostname}:{os.getpid()}.log"
            fs_path = os.path.join(logging_dir, logging_file)

        os.makedirs(os.path.dirname(fs_path), exist_ok=True)

        file_handler = CustomRotatingFileHandler(fs_path, maxBytes=1e6)
        file_handler.setLevel(fs_level)
        file_handler.setFormatter(formatter)
        logging.root.addHandler(file_handler)

    if enable_db:
        db_handler = LogServerHandler()
        db_handler.setLevel(db_level)
        logging.root.addHandler(db_handler)

    if console_level is None:
        console_level = os.environ.get("LOGLEVEL", "WARNING")
        console_level = logging.getLevelName(console_level)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)

    logging.root.setLevel(logging.DEBUG)
    logging.root.addHandler(console_handler)

    enable_exception_handler()


__all__ = ["enable_logging"]
