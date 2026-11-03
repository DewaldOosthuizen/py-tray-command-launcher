# Icon assets

The application uses a compact, high-contrast icon family designed for launcher and
tray-menu sizes. The main application mark is a command window with a launch chevron;
category and menu icons use simple navy, teal, and amber pictograms.

## Asset map

| Purpose | Asset |
|---|---|
| Main application, window, and tray icon | `resources/icons/branding/icon.png` |
| Legacy tray-icon fallback | `resources/icons/icon.png` |
| Default command categories | `resources/icons/categories/{system,media,studies,utilities,development,networking}.png` |
| Fixed tray-menu groups | `resources/icons/menu/{favorites,recent,management,tools}.png` |

The old category JPEG assets have been removed. The shipped defaults and inline fallback
configuration use the new PNG paths. If a custom `commands.json` still references an old
JPEG path, the icon resolver falls back to the main application icon; update those paths to
`icons/categories/<category>.png` to restore category-specific artwork.

Tray-menu entries and their nested menus render icons at 18 logical pixels through a
`QProxyStyle` metric override, preserving the active Qt style and theme.

## Packaging

`py-tray-command-launcher.spec` bundles the full `resources/` directory, so category and
menu icons are available in source runs and PyInstaller builds. Release packaging also
uses the branding icon for the desktop entry and packaged launcher icon. To replace or add
an icon, keep its configured path under `resources/icons/` and use transparent PNG for
menu artwork; then verify the resource path and packaged output.
