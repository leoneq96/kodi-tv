# -*- coding: utf-8 -*-
# Module: service.netflixlike.helper
# Author: NetflixLike Project
# License: GPL v3.0

import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs
import json
import os
import time
from urllib.parse import parse_qs, urlparse

from router import Router
from kodiutils import log, get_kodi_version
from database import Database
from profiles import ProfileManager
from mylist import MyList
from continuewatching import ContinueWatching
from providers.fanfilm import FanFilmProvider
from providers.kodilibrary import KodiLibraryProvider


ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_PATH = ADDON.getAddonInfo('path')
HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]


def get_active_profile():
    """Get the currently active Kodi profile name."""
    return xbmc.getInfoLabel('System.ProfileName')


def get_profile_path():
    """Get the profile-specific data path."""
    profile = get_active_profile()
    addon = xbmcaddon.Addon()
    profile_path = xbmcvfs.translatePath(f"{addon.getAddonInfo('profile')}/{profile}")
    if not xbmcvfs.exists(profile_path):
        xbmcvfs.mkdirs(profile_path)
    return profile_path


def get_data_file():
    """Get the data file path for the current profile."""
    return os.path.join(get_profile_path(), 'data.json')


def load_data():
    """Load data for current profile."""
    data_file = get_data_file()
    if xbmcvfs.exists(data_file):
        try:
            content = xbmcvfs.File(data_file, 'r').read()
            return json.loads(content)
        except Exception as e:
            log(f"Error loading data: {e}")
    return {'my_list': [], 'settings': {}}


def save_data(data):
    """Save data for current profile."""
    data_file = get_data_file()
    try:
        xbmcvfs.File(data_file, 'w').write(json.dumps(data, ensure_ascii=False, indent=2))
        return True
    except Exception as e:
        log(f"Error saving data: {e}")
        return False