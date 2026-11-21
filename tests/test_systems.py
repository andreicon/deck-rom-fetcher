from romfetcher import systems


def test_load_ps2_mapping_and_list_titles():
    systems_map = systems.load_systems("config/systems.yaml")
    mapping = systems.get_mapping(systems_map, "PS2")
    assert mapping["emudeck_dir"] == "ps2"
    titles = systems.list_redump_titles("data/redump/ps2.tsv")
    assert len(titles) >= 3
    assert titles[0]["title"] and titles[0]["region"]
