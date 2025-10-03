from crawler.core import utils


def test_stable_hash_changes_with_input():
    value1 = utils.stable_hash({"a": 1})
    value2 = utils.stable_hash({"a": 2})
    assert value1 != value2


def test_fuzzy_equal():
    assert utils.fuzzy_equal("Example", "example")
    assert not utils.fuzzy_equal("Example", "Different", threshold=0.9)
