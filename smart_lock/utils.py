import logging
from os import environ

logger = logging.getLogger(__name__)


def get_postgres_host_configuration_dict():
    configuration = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": environ.get("POSTGRES_DB", "smart_lock"),
        "USER": environ.get("POSTGRES_USER", "smart_lock"),
        "PASSWORD": environ.get("POSTGRES_PASSWORD", "smart_lock"),
        "HOST": environ.get("POSTGRES_HOST", "localhost"),
        "PORT": environ.get("POSTGRES_PORT", "5432"),
    }

    logger.info(f"Postgres configuration is {configuration}")
    return configuration
