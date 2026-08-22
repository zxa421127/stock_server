# -*- coding: utf-8 -*-
"""Web-only Waitress launcher for zero-downtime candidate validation."""

import logging

from waitress import serve

import config
from app import app, setup_logging


def main() -> None:
    setup_logging()

    logging.info(
        "Web-only Waitress start: http://%s:%s threads=%s",
        config.SERVER_HOST,
        config.SERVER_PORT,
        config.SERVER_THREADS,
    )

    serve(
        app,
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        threads=config.SERVER_THREADS,
        connection_limit=config.WAITRESS_CONNECTION_LIMIT,
        channel_timeout=config.WAITRESS_CHANNEL_TIMEOUT,
        backlog=config.WAITRESS_BACKLOG,
        expose_tracebacks=False,
    )


if __name__ == "__main__":
    main()
