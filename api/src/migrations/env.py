"""Environment setup for alembic config."""

from collections.abc import Sequence
from logging.config import fileConfig

from alembic import context
from geoalchemy2 import alembic_helpers
from sqlalchemy import MetaData, engine_from_config, pool

from src.app.config import DatabaseSettings  # pyright: ignore [reportUnknownVariableType, reportMissingImports]
from src.migrations.utils import include_name, process_revision_directives, update_history
from src.models import Base  # pyright: ignore [reportUnknownVariableType, reportMissingImports]

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata


target_metadata: Sequence[MetaData] = [Base.metadata]

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    db_settings = DatabaseSettings()
    url: str = str(db_settings.db_url)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        process_revision_directives=process_revision_directives,
        on_version_apply=update_history,
        include_name=include_name,
        # Add in geoalchemy helpers according to https://geoalchemy-2.readthedocs.io/en/latest/alembic.html#helpers
        include_object=alembic_helpers.include_object,
        render_item=alembic_helpers.render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    db_settings = DatabaseSettings()  # pyright: ignore [reportUnknownVariableType, reportCallIssue]
    url: str = str(db_settings.db_url)  # pyright: ignore [reportUnknownMemberType, reportUnknownArgumentType]
    connectable = engine_from_config(
        {"sqlalchemy.url": url},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            process_revision_directives=process_revision_directives,
            on_version_apply=update_history,
            include_name=include_name,
            # Add in geoalchemy helpers according to https://geoalchemy-2.readthedocs.io/en/latest/alembic.html#helpers
            include_object=alembic_helpers.include_object,
            render_item=alembic_helpers.render_item,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
