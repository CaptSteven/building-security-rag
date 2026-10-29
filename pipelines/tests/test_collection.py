import pytest
pytest.importorskip("bs4", reason="collection dependency group not installed")
from pipelines.collection.collect_sample import robots_allowed


def test_robots_matching_restrictions_and_specific_allow():
    robots='User-agent: *\nDisallow: /private/\nAllow: /private/public/\nDisallow: /*.pdf$'
    assert not robots_allowed(robots,'https://example.com/private/file')
    assert robots_allowed(robots,'https://example.com/private/public/file')
    assert not robots_allowed(robots,'https://example.com/manual/a.pdf')
    assert robots_allowed(robots,'https://example.com/products/camera')


def test_robots_does_not_inherit_other_agents_rules():
    robots='User-agent: *\nDisallow: /private/\nUser-agent: OtherBot\nDisallow: /'
    assert robots_allowed(robots,'https://example.com/public')
    assert not robots_allowed(robots,'https://example.com/private/x')
