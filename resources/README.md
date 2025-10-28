# Menu Bar Icons

This directory contains icons for the macOS menu bar application.

## Icon Requirements

The menu bar app needs 5 cloud icon states:

1. **icon_cloud_gray.png** - Idle/disabled state (app not running sync)
2. **icon_cloud_yellow.png** - Syncing state (sync in progress)
3. **icon_cloud_green.png** - Success state (sync completed successfully)
4. **icon_cloud_red.png** - Error state (sync failed)
5. **icon_cloud.png** - Default/base icon

## Specifications

- **Size**: 22x22 pixels (standard macOS menu bar icon size)
- **Format**: PNG with transparency
- **Style**: Simple, monochrome-friendly (menu bar adapts to light/dark mode)
- **Color coding**:
  - Gray: #808080 (idle)
  - Yellow: #FDB913 (syncing)
  - Green: #28A745 (success)
  - Red: #DC3545 (error)

## Development Note

For initial development and testing, the menu bar app uses emoji icons:
- ☁️ (cloud) - Base icon for all states
- The app will use the text color/tint to indicate state

To add custom PNG icons:
1. Create or download cloud icons matching the specifications above
2. Place them in this directory
3. Update `src/menu_bar_app.py` to load PNG files instead of emoji

## Recommended Tools

- [SF Symbols](https://developer.apple.com/sf-symbols/) - Apple's icon library
- [IconJar](https://geticonjar.com/) - Icon management
- Sketch, Figma, or Adobe Illustrator for custom design
