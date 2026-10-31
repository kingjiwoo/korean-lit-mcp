from importlib import import_module
from importlib.metadata import version


def test_package_is_importable() -> None:
    import_module("korean_lit_mcp")
    assert version("korean-lit-mcp")
