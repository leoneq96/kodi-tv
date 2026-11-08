# -*- coding: utf-8 -*-
# Module: kodiutils
# Author: NetflixLike Project
# License: GPL v3.0

import xbmc
import xbmcaddon
import xbmcvfs


ADDON = xbmcaddon.Addon()


def log(message, level=xbmc.LOGINFO):
    """Log message with addon prefix."""
    xbmc.log(f"[NetflixLike Helper] {message}", level)


def get_kodi_version():
    """Get Kodi version."""
    return xbmc.getInfoLabel("System.BuildVersion")


def get_addon_version():
    """Get addon version."""
    return xbmcaddon.Addon().getAddonInfo('version')


def get_addon_path():
    """Get addon path."""
    return xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('path'))


def get_profile_path():
    """Get addon profile path."""
    return xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))