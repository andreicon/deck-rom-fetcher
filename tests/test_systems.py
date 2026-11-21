from romfetcher import systems


def test_load_ps2_mapping():
    systems_map = systems.load_systems("config/systems.yaml")
    mapping = systems.get_mapping(systems_map, "PS2")
    assert mapping["emudeck_dir"] == "ps2"
