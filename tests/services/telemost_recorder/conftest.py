import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--url", help="Telemost meeting URL for live integration tests")


@pytest.fixture
def telemost_url(request: pytest.FixtureRequest) -> str:
    url = request.config.getoption("--url", default=None)
    if not url:
        pytest.skip("Pass --url=<telemost_url> to run live integration tests")
    return url
