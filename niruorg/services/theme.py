from __future__ import annotations

import colorsys
import os
import shutil
import tomllib
from pathlib import Path
from typing import Any

FALLBACK = {
    'bg': '#0f0f10',
    'fg': '#e5e5e5',
    'muted': '#a8a8a8',
    'panel': '#161618',
    'surface': '#1d1d20',
    'border': '#2a2a2d',
    'accent': '#819eb5',
    'accentfg': '#0f0f10',
    'sel': '#26262a',
    'danger': '#d77a7a',
}


def config_home() -> Path:
    return Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')


def theme_paths() -> dict[str, Path]:
    config = config_home()
    return {
        'appearance': config / 'niruwm' / 'appearance.toml',
        'niruwm_config': config / 'niruwm' / 'config.toml',
        'kitty': config / 'nirux' / 'theme' / 'kitty.conf',
    }


def nirux_available() -> bool:
    paths = theme_paths()
    return bool(
        shutil.which('niructl')
        or paths['appearance'].exists()
        or paths['kitty'].exists()
        or (config_home() / 'nirux').is_dir()
    )


def default_theme() -> str:
    return 'Follow NIRUX' if nirux_available() else 'Niru Noir'


def _hex(value: Any, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    value = value.strip().strip('"\'')
    if not value:
        return fallback
    if not value.startswith('#'):
        value = '#' + value
    if len(value) == 7 and all(c in '0123456789abcdefABCDEF' for c in value[1:]):
        return value.lower()
    if len(value) == 4 and all(c in '0123456789abcdefABCDEF' for c in value[1:]):
        return '#' + ''.join(c * 2 for c in value[1:]).lower()
    return fallback


def _rgb(value: str) -> tuple[int, int, int]:
    value = _hex(value, '#000000')
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def _hex_rgb(rgb: tuple[float, float, float]) -> str:
    return '#' + ''.join(f'{max(0, min(255, round(v))):02x}' for v in rgb)


def mix(first: str, second: str, weight: float) -> str:
    weight = max(0.0, min(1.0, weight))
    a, b = _rgb(first), _rgb(second)
    return _hex_rgb(tuple(a[i] * (1 - weight) + b[i] * weight for i in range(3)))


def luminance(value: str) -> float:
    def channel(v: int) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(value)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(first: str, second: str) -> float:
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def readable_on(background: str, candidates: tuple[str, ...] = ('#ffffff', '#000000')) -> str:
    ranked = sorted(candidates, key=lambda color: contrast(background, color), reverse=True)
    return ranked[0]


def _appearance(path: Path) -> dict[str, Any]:
    try:
        with path.open('rb') as handle:
            data = tomllib.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _kitty(path: Path) -> dict[str, str]:
    colors: dict[str, str] = {}
    try:
        lines = path.read_text(errors='replace').splitlines()
    except Exception:
        return colors
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#') or len(line.split()) < 2:
            continue
        key, value = line.split(None, 1)
        if key in {
            'background', 'foreground', 'color0', 'color1', 'color4', 'color6',
            'color7', 'color8', 'selection_background', 'selection_foreground',
            'cursor', 'cursor_text_color',
        }:
            colors[key] = value.strip()
    return colors


def _metrics(appearance: dict[str, Any]) -> dict[str, int]:
    font = appearance.get('font') if isinstance(appearance.get('font'), dict) else {}
    spacing = appearance.get('spacing') if isinstance(appearance.get('spacing'), dict) else {}
    focus = appearance.get('focus') if isinstance(appearance.get('focus'), dict) else {}
    try:
        size = float(font.get('size', 13.0))
    except Exception:
        size = 13.0
    try:
        padding = int(spacing.get('padding', 5))
    except Exception:
        padding = 5
    try:
        focus_width = int(focus.get('width', 1))
    except Exception:
        focus_width = 1
    return {
        'font_size': max(11, min(16, round(size))),
        'padding': max(3, min(10, round(padding / 2))),
        'focus_width': max(1, min(3, focus_width)),
    }


def load_nirux_palette(paths: dict[str, Path] | None = None) -> dict[str, str]:
    paths = paths or theme_paths()
    appearance = _appearance(paths['appearance'])
    kitty = _kitty(paths['kitty'])
    colors = appearance.get('colors') if isinstance(appearance.get('colors'), dict) else {}
    palette = dict(FALLBACK)
    if kitty:
        palette.update({
            'bg': _hex(kitty.get('background'), palette['bg']),
            'fg': _hex(kitty.get('foreground'), palette['fg']),
            'muted': _hex(kitty.get('color8'), palette['muted']),
            'border': mix(_hex(kitty.get('color0'), palette['bg']), _hex(kitty.get('color8'), palette['border']), 0.55),
            'accent': _hex(kitty.get('color4'), palette['accent']),
            'sel': _hex(kitty.get('selection_background'), palette['sel']),
            'danger': _hex(kitty.get('color1'), palette['danger']),
            'surface': mix(_hex(kitty.get('background'), palette['bg']), _hex(kitty.get('foreground'), palette['fg']), 0.07),
            'panel': mix(_hex(kitty.get('background'), palette['bg']), _hex(kitty.get('foreground'), palette['fg']), 0.035),
        })
    if colors:
        palette.update({
            'bg': _hex(colors.get('background'), palette['bg']),
            'fg': _hex(colors.get('foreground'), palette['fg']),
            'muted': _hex(colors.get('muted'), palette['muted']),
            'border': _hex(colors.get('border'), palette['border']),
            'accent': _hex(colors.get('focus') or colors.get('accent'), palette['accent']),
            'sel': _hex(colors.get('selected'), palette['sel']),
            'danger': _hex(colors.get('error'), palette['danger']),
            'panel': _hex(colors.get('surface'), palette['panel']),
            'surface': _hex(colors.get('surface'), palette['surface']),
        })
    palette['accentfg'] = readable_on(palette['accent'])
    if contrast(palette['bg'], palette['fg']) < 4.5:
        palette['fg'] = readable_on(palette['bg'])
    if contrast(palette['panel'], palette['fg']) < 3.0:
        palette['fg'] = readable_on(palette['panel'])
    if contrast(palette['sel'], palette['fg']) < 3.0:
        palette['sel'] = mix(palette['bg'], palette['accent'], 0.35)
    return palette


def load_nirux_metrics(paths: dict[str, Path] | None = None) -> dict[str, int]:
    paths = paths or theme_paths()
    return _metrics(_appearance(paths['appearance']))
