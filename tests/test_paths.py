from romfetcher import paths


def test_find_roms_root_prefers_settings_and_falls_back(tmp_path):
    home = tmp_path / "home"
    (home / "Emulation" / "roms" / "psx").mkdir(parents=True)
    (home / "Emulation" / "bios").mkdir(parents=True)
    settings = tmp_path / "settings.sh"
    settings.write_text('romsPath="$HOME/Emulation/roms"\n')
    found = paths.find_roms_root(str(home), str(settings), [])
    assert found.endswith("Emulation/roms")
    assert paths.rom_dir_for("/r/roms", "ps2") == "/r/roms/ps2"
    assert paths.free_bytes(str(tmp_path)) > 0


def test_settings_split_quote_form_parses_cleanly(tmp_path):
    home = tmp_path / "home"
    sea = tmp_path / "run" / "media" / "deck" / "GD2S5" / "Emulation" / "roms"
    (sea / "ps2").mkdir(parents=True)
    settings = tmp_path / "settings.sh"
    settings.write_text('romsPath="/run/media/deck/GD2S5"/Emulation/roms\n')
    line = 'romsPath="/run/media/deck/GD2S5"/Emulation/roms'
    parsed = paths._parse_settings_roms_path(str(settings), "/x")
    assert parsed == "/run/media/deck/GD2S5/Emulation/roms"
    found = paths.find_roms_root(
        str(home), str(settings),
        [str(tmp_path / "run" / "media" / "deck" / "*" / "Emulation" / "roms")])
    assert found == str(sea)
