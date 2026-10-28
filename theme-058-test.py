#!/usr/bin/env python3
import os
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    config = root / 'config'
    os.environ['XDG_CONFIG_HOME'] = str(config)
    (config / 'niruwm').mkdir(parents=True)
    (config / 'nirux' / 'theme').mkdir(parents=True)
    from niruorg.services.theme import (
        contrast, default_theme, load_nirux_metrics, load_nirux_palette,
        nirux_available, theme_paths,
    )

    assert nirux_available()
    assert default_theme() == 'Follow NIRUX'
    kitty = config / 'nirux' / 'theme' / 'kitty.conf'
    kitty.write_text('background #0f0f10\nforeground #e5e5e5\ncolor1 #b87878\ncolor4 #819eb5\ncolor8 #808086\nselection_background #3a3a3d\n')
    appearance = config / 'niruwm' / 'appearance.toml'
    appearance.write_text('[font]\nsize = 15.0\n[spacing]\npadding = 12\n[focus]\nwidth = 2\n')
    dark = load_nirux_palette(theme_paths())
    assert dark['bg'] == '#0f0f10' and dark['fg'] == '#e5e5e5'
    assert dark['accent'] == '#819eb5' and dark['danger'] == '#b87878'
    assert contrast(dark['bg'], dark['fg']) >= 4.5
    metrics = load_nirux_metrics(theme_paths())
    assert metrics == {'font_size': 15, 'padding': 6, 'focus_width': 2}

    appearance.write_text('[colors]\nbackground = "f3ece0"\nforeground = "3b3228"\nmuted = "7d6f5f"\nborder = "d8cdbb"\nfocus = "a63d2f"\nselected = "e0d3bf"\nerror = "9c3d32"\nsurface = "f8f2e8"\n[font]\nsize = 14\n[spacing]\npadding = 8\n[focus]\nwidth = 1\n')
    light = load_nirux_palette(theme_paths())
    assert light['bg'] == '#f3ece0' and light['fg'] == '#3b3228'
    assert contrast(light['bg'], light['fg']) >= 4.5
    assert contrast(light['accent'], light['accentfg']) >= 4.5
    assert light['panel'] == '#f8f2e8'

    kitty.write_text('broken line\n')
    appearance.write_text('not valid toml = [')
    fallback = load_nirux_palette(theme_paths())
    assert fallback['bg'] == '#0f0f10' and fallback['fg'] == '#e5e5e5'
print('NIRUX theme contract OK')
