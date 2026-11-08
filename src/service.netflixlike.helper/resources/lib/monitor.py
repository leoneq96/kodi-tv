# -*- coding: utf-8 -*-
# Module: monitor
# Author: NetflixLike Project
# License: GPL v3.0

"""
Monitor class for NetflixLike Helper service.
This class inherits from xbmc.Monitor and implements the main service loop.
"""

import xbmc
import xbmcaddon
import xbmcvfs
import json
import os
import sys
import time
import traceback
from threading import Thread

# Lazy imports to avoid import errors at module level
def import_resources():
    from resources.lib.router import Router
    from resources.lib.kodiutils import log, get_kodi_version
    from resources.lib.database import Database
    from resources.lib.profiles import ProfileManager
    from resources.lib.mylist import MyList
    from resources.lib.continuewatching import ContinueWatching
    from resources.lib.providers.fanfilm import FanFilmProvider
    from resources.lib.providers.kodilibrary import KodiLibraryProvider
    return {
        'Router': Router,
        'log': log,
        'get_kodi_version': get_kodi_version,
        'Database': Database,
        'ProfileManager': ProfileManager,
        'MyList': MyList,
        'ContinueWatching': ContinueWatching,
        'FanFilmProvider': FanFilmProvider,
        'KodiLibraryProvider': KodiLibraryProvider,
    }

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_PATH = ADDON.getAddonInfo('path')
PROFILE_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
DATA_FILE = os.path.join(PROFILE_PATH, 'data.json')


def get_active_profile():
    """Get the currently active Kodi profile name."""
    return xbmc.getInfoLabel('System.ProfileName')


def initialize_addon():
    """Initialize addon directories and data file."""
    try:
        if not xbmcvfs.exists(PROFILE_PATH):
            xbmcvfs.mkdirs(PROFILE_PATH)

        if not xbmcvfs.exists(DATA_FILE):
            default_data = {
                'my_list': [],
                'settings': {
                    'auto_refresh': True,
                    'max_continue_items': 20,
                    'max_list_items': 50
                }
            }
            xbmcvfs.File(DATA_FILE, 'w').write(json.dumps(default_data, ensure_ascii=False, indent=2))

        # Ensure database is initialized
        resources = import_resources()
        resources['Database']().init()
    except Exception as e:
        xbmc.log(f"[NetflixLike Helper] Error in initialize_addon: {e}", xbmc.LOGERROR)
        xbmc.log(f"[NetflixLike Helper] Traceback: {traceback.format_exc()}", xbmc.LOGERROR)


class NetflixLikeMonitor(xbmc.Monitor):
    """Main monitor that runs on login and handles profile changes."""

    def __init__(self):
        """Constructor for Monitor"""
        super().__init__()
        try:
            resources = import_resources()
            self.log_func = resources['log']
            self.profile_manager = resources['ProfileManager']()
            self.current_profile = get_active_profile()
            self.log_func(f"NetflixLike Helper started for profile: {self.current_profile}")
            initialize_addon()
        except Exception as e:
            xbmc.log(f"[NetflixLike Helper] Error in Monitor.__init__: {e}", xbmc.LOGERROR)
            xbmc.log(f"[NetflixLike Helper] Traceback: {traceback.format_exc()}", xbmc.LOGERROR)

    def onSettingsChanged(self):
        try:
            resources = import_resources()
            log_func = resources['log']
            log_func("Settings changed, reloading...")
        except Exception as e:
            xbmc.log(f"[NetflixLike Helper] Error in onSettingsChanged: {e}", xbmc.LOGERROR)

    def onProfileChanged(self):
        try:
            resources = import_resources()
            log_func = resources['log']
            old_profile = self.current_profile
            self.current_profile = get_active_profile()
            log_func(f"Profile changed from {old_profile} to {self.current_profile}")
            self.profile_manager.load_profile(self.current_profile)
        except Exception as e:
            xbmc.log(f"[NetflixLike Helper] Error in onProfileChanged: {e}", xbmc.LOGERROR)

    def onScreensaverDeactivated(self):
        pass

    def run(self):
        """Main service loop"""
        self.log_func('Service started', 0)

        while not self.abortRequested():
            # check every 10 sec
            if self.waitForAbort(10):
                # Abort was requested while waiting. We should exit
                break

        self.log_func('Service stopped', 0)