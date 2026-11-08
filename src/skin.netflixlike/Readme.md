# NetflixLike

A Netflix-style, row-based Kodi skin, forked from **Arctic Fuse 2 v2.12.11** by
[jurialmunkey](https://github.com/jurialmunkey/skin.arctic.fuse.2).

This fork is intended for a TV driven by a standard remote (arrows / OK / Back).
The mouse/touch mode inherited from Arctic Fuse 2 stays off by default.

## Changes compared to Arctic Fuse 2 v2.12.11

- New add-on id and name: `skin.netflixlike` / **NetflixLike**, version `1.0.0`.
- All references to the old skin id were renamed, including the skinvariables
  generator and the per-user skin folder.
- Heavy home-screen animations were removed:
  - focus bounce (zoom + fade) on every arrow press is now instant,
  - slide transitions of the home hub groups / widgets are now instant,
  - the 85% -> 100% zoom when a view/hub group becomes visible is now instant,
  - the full-screen fanart cross-fade (`background_fadetime`) is now instant.
- Small, cheap effects (menu fade, list bumper) are unchanged.
- `extras/`, `fonts/`, `media/`, `shortcuts/` and the original icon/fanart are
  kept from upstream so the skin looks and behaves like Arctic Fuse 2.

## Requirements

| Add-on | Minimum |
| --- | --- |
| `xbmc.gui` | 5.17.0 |
| `script.skinvariables` | 2.1.28 |
| `script.texturemaker` | 0.2.9 |
| `plugin.video.themoviedb.helper` | 6.12.1 |
| `resource.images.weathericons.white` | 0.0.1 |
| `resource.images.studios.coloured` | 0.0.1 |
| `resource.font.robotocjksc` | 0.0.3 |

`script.skinshortcuts` is not required by this skin, but it is supported and is
installed by `../deploy.sh` so custom menu shortcuts keep working.

The dependency zips are downloaded from the official Kodi add-on mirror
(`mirrors.kodi.tv/addons/piers/`) and from jurialmunkey's alpha repository.

## Install

The skin is deployed to the TV with `../deploy.sh` (see that script for the
flags). It can also be installed manually by copying this folder to
`<kodi>/.kodi/addons/skin.netflixlike/` and restarting Kodi.

## License and attribution

This work is licensed under the
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 Unported License](http://creativecommons.org/licenses/by-nc-sa/4.0/).
It is a derivative of Arctic Fuse 2 by jurialmunkey, and the original license
and attribution are preserved in `LICENSE.txt` and in this file.
