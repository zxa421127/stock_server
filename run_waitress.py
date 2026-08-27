# -*- coding: utf-8 -*-
"""Recommended Windows production launcher."""
import logging
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")


from waitress import serve

import config
from app import app, setup_logging, start_runtime_services

if __name__ == "__main__":
    setup_logging()
    start_runtime_services()
    logging.info(
        "Waitress启动: env=%s http://%s:%s threads=%s",
        config.APP_ENV,
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
        trusted_proxy="127.0.0.1",
        trusted_proxy_count=1,
        trusted_proxy_headers={
            "x-forwarded-for",
            "x-forwarded-proto",
        },
        clear_untrusted_proxy_headers=True,
        expose_tracebacks=False,
    )
