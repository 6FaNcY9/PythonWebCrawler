from crawler.adapters.youtube_free import _parse_iso_duration


def test_parse_iso_duration():
    assert _parse_iso_duration("PT1H2M3S") == 3723
    assert _parse_iso_duration("PT45M") == 2700
    assert _parse_iso_duration(None) == 0
