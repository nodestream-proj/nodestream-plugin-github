import logging

from nodestream_github.util.permissions import PermissionCategory, PermissionName


class _CustomLogger(logging.Filterer):
    def __init__(self, base_logger: logging.Logger):
        self._logger = base_logger

    @property
    def logger(self) -> logging.Logger:
        return self._logger

    @property
    def handlers(self) -> list[logging.Handler]:
        return self._logger.handlers

    def permission_warning(
        self,
        endpoint_title: str,
        current_item: str,
        permission_name: PermissionName,
        permission_category: PermissionCategory,
        role: str = "read",
        **kwargs,
    ):
        self.logger.warning(
            "Current token cannot access %s permissions for %s. "
            'Fine-grained access tokens must include the "%s" %s permissions (%s)',
            endpoint_title,
            current_item,
            permission_name.title(),
            permission_category.title(),
            role,
            kwargs,
        )

    def debug(self, msg, *args, **kwargs):
        self.logger.debug(msg, stacklevel=2, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.logger.warning(msg, stacklevel=2, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.logger.info(msg, stacklevel=2, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.logger.error(msg, stacklevel=2, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self.logger.critical(msg, stacklevel=2, *args, **kwargs)

    def log(self, level, msg, *args, **kwargs):
        self.logger.log(level, msg, stacklevel=2, *args, **kwargs)


def init_logger(name: str) -> _CustomLogger:
    logger = _CustomLogger(logging.getLogger(name))
    return logger
