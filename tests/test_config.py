import json

import pytest

from apartment_search.config import ConfigError, load_config, write_default_config


def test_write_and_load_default_config(tmp_path):
    path = tmp_path / "config.json"

    write_default_config(path)
    config = load_config(path)

    assert config.criteria.work_address == "HaHaskala 3, Tel Aviv"
    assert config.sources[0].type == "json"


def test_load_config_requires_sources(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"sources": []}), encoding="utf-8")

    with pytest.raises(ConfigError, match="at least one source"):
        load_config(path)
