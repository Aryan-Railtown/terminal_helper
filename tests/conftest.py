import os

import pytest


@pytest.fixture(autouse=True)
def _restore_environ():
    """cli.main sets SAGE_DEBUG / RAILTRACKS_* in os.environ; don't let that leak across tests."""
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
