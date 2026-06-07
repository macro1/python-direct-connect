from typing import Iterable
from typing import cast

import pytest
from testcontainers.compose import DockerCompose


@pytest.fixture(scope="session")
def compose_env() -> Iterable[DockerCompose]:
    compose = DockerCompose("tests/services", compose_file_name="compose.yaml")
    with compose:
        yield compose


@pytest.fixture(scope="session")
def nmdc_host_and_port(compose_env: DockerCompose) -> tuple[str, str]:
    return cast(
        tuple[str, str], compose_env.get_service_host_and_port("nmdc", port=411)
    )


@pytest.fixture(scope="session")
def adc_host_and_port(compose_env: DockerCompose) -> tuple[str, str]:
    return cast(
        tuple[str, str], compose_env.get_service_host_and_port("adc", port=1511)
    )
