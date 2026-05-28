from typing import Iterable
from typing import Optional

import pytest
from testcontainers.compose import DockerCompose


@pytest.fixture(scope="session")
def nmdc_host_and_port() -> Iterable[tuple[Optional[str], Optional[int]]]:
    nmdc_compose = DockerCompose("tests/services", compose_file_name="compose.yaml")
    with nmdc_compose:
        yield nmdc_compose.get_service_host_and_port("nmdc", port=411)
