import getpass
import logging
import os
import socket
import sys
from contextlib import suppress
from datetime import datetime
from urllib.parse import urljoin

import requests


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


def enable_logging(enable_fs=True, fs_path=None, fs_level=logging.INFO, enable_db=True, db_level=logging.INFO):
    """Enables the default C-AD logging configuration for Python programs
    Defaults to database logging, filesystem logging optional

    Args:
        enable_db (bool, optional): Enables logging to database server. Defaults to True.
        enable_fs (bool, optional): Enables logging to filesystem text file. Defaults to False.
        fs_path (str, optional): Path to log file used if enable_fs=True. Defaults to /operations/app_store/<program>/diagnostics/message.
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

        file_handler = logging.FileHandler(fs_path)
        file_handler.setLevel(fs_level)
        file_handler.setFormatter(formatter)
        logging.root.addHandler(file_handler)

    if enable_db:
        db_handler = LogServerHandler()
        db_handler.setLevel(db_level)
        logging.root.addHandler(db_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)

    logging.root.setLevel(logging.DEBUG)
    logging.root.addHandler(console_handler)

    enable_exception_handler()


__all__ = ["LogServerHandler", "enable_exception_handler", "enable_logging"]

