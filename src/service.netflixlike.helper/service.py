# -*- coding: utf-8 -*-
# Module: service.netflixlike.helper
# Author: NetflixLike Project
# License: GPL v3.0

import xbmc
import xbmcaddon
import xbmcvfs
import json
import os
import sys
import time
import traceback
from threading import Thread

# Add resources/lib to path
ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
sys.path.insert(0, os.path.join(ADDON_PATH, 'resources', 'lib'))

from resources.lib.router import Router
from resources.lib.kodiutils import log, get_kodi_version
from resources.lib.database import Database
from resources.lib.profiles import ProfileManager
from resources.lib.mylist import MyList
from resources.lib.continuewatching import ContinueWatching
from resources.lib.providers.fanfilm import FanFilmProvider
from resources.lib.providers.kodilibrary import KodiLibraryProvider


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
        Database().init()
    except Exception as e:
        xbmc.log(f"[NetflixLike Helper] Error in initialize_addon: {e}", xbmc.LOGERROR)
        xbmc.log(f"[NetflixLike Helper] Traceback: {traceback.format_exc()}", xbmc.LOGERROR)


class Monitor(xbmc.Monitor):
    """Main monitor that runs on login and handles profile changes."""

    def __init__(self):
        xbmc.Monitor.__init__(self)
        try:
            self.profile_manager = ProfileManager()
            self.current_profile = get_active_profile()
            log(f"NetflixLike Helper started for profile: {self.current_profile}")
            initialize_addon()
        except Exception as e:
            xbmc.log(f"[NetflixLike Helper] Error in Monitor.__init__: {e}", xbmc.LOGERROR)
            xbmc.log(f"[NetflixLike Helper] Traceback: {traceback.format_exc()}", xbmc.LOGERROR)

    def onSettingsChanged(self):
        try:
            log("Settings changed, reloading...")
        except Exception as e:
            xbmc.log(f"[NetflixLike Helper] Error in onSettingsChanged: {e}", xbmc.LOGERROR)

    def onProfileChanged(self):
        try:
            old_profile = self.current_profile
            self.current_profile = get_active_profile()
            log(f"Profile changed from {old_profile} to {self.current_profile}")
            self.profile_manager.load_profile(self.current_profile)
        except Exception as e:
            xbmc.log(f"[NetflixLike Helper] Error in onProfileChanged: {e}", xbmc.LOGERROR)

    def onScreensaverDeactivated(self):
        pass


def main():
    """Main service entry point - called by Kodi on startup."""
    try:
        log("Starting NetflixLike Helper service...")
        initialize_addon()

        monitor = Monitor()

        # Keep service running until Kodi requests abort
        while not monitor.abortRequested():
            if monitor.waitForAbort(10):
                break

        log("NetflixLike Helper service stopped.")
    except Exception as e:
        xbmc.log(f"[NetflixLike Helper] Fatal error in main: {e}", xbmc.LOGFATAL)
        xbmc.log(f"[NetflixLike Helper] Traceback: {traceback.format_exc()}", xbmc.LOGFATAL)


# Entry point - Kodi calls this when starting the service
if __name__ == '__main__':
    main()