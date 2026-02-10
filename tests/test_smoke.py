from proteus.core.smoke import run_smoke_check


def test_smoke_check_returns_ok() -> None:
    assert run_smoke_check() == "smoke-ok"
