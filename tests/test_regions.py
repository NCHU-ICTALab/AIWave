from core.data.regions import resolve


def test_resolves_official_region_sample() -> None:
    region = resolve("大同區", "台北市")
    assert region is not None
    assert region["county_code"] == "01"
    assert region["district_code"] == "002"


def test_resolves_namespaced_taichung_demo_extension_and_normalizes_tai() -> None:
    region = resolve("西屯區", "臺中市")
    assert region is not None
    assert region == {
        "county_code": "08",
        "county_name": "台中市",
        "district_code": "seed-taichung-xitun",
        "district_name": "西屯區",
    }
