import logging

log = logging.getLogger(__name__)


def flush() -> None:
    log.debug("notifier tick")
