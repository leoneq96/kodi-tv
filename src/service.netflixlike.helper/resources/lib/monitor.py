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

# Direct imports from same directory (resources/lib/)
# Kodi adds the addon's resources/lib to sys.path when loading the service
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


class NetflixLikeMonitor(xbmc.Monitor):
    """Main monitor that runs on login and handles profile changes."""

    def __init__(self):
        """Constructor for Monitor"""
        super().__init__()
        try:
            # Initialize addon directories first, before creating ProfileManager
            initialize_addon()
            self.log_func = log
            self.profile_manager = ProfileManager()
            self.current_profile = get_active_profile()
            self.log_func(f"NetflixLike Helper started for profile: {self.current_profile}")
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

    def run(self):
        """Main service loop"""
        try:
            self.log_func('Service started', 0)
            xbmc.log("[NetflixLike Helper] monitor.run: Service started logged", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[NetflixLike Helper] monitor.run: Error logging 'Service started': {e}", xbmc.LOGERROR)
            xbmc.log(f"[NetflixLike Helper] monitor.run: Traceback: {traceback.format_exc()}", xbmc.LOGERROR)

        loop_count = 0
        while not self.abortRequested():
            loop_count += 1
            try:
                xbmc.log(f"[NetflixLike Helper] monitor.run: Loop iteration {loop_count}, abortRequested={self.abortRequested()}", xbmc.LOGDEBUG)
            except Exception as e:
                xbmc.log(f"[NetflixLike Helper] monitor.run: Error logging loop: {e}", xbmc.LOGERROR)
            
            # check every 10 sec
            try:
                abort = self.waitForAbort(10)
                xbmc.log(f"[NetflixLike Helper] monitor.run: waitForAbort returned {abort}, abortRequested={self.abortRequested()}", xbmc.LOGDEBUG)
            except Exception as e:
                xbmc.log(f"[NetflixLike Helper] monitor.run: Exception in waitForAbort: {e}", xbmc.LOGERROR)
                xbmc.log(f"[NetflixLike Helper] monitor.run: Traceback: {traceback.format_exc()}", xbmc.LOGERROR)
                break
            
            if abort:
                # Abort was requested while waiting. We should exit
                try:
                    self.log_func('Abort requested, exiting', 0)
                except Exception as e:
                    xbmc.log(f"[NetflixLike Helper] monitor.run: Error logging 'Abort requested': {e}", xbmc.LOGERROR)
                break

        try:
            self.log_func('Service stopped', 0)
        except Exception as e:
            xbmc.log(f"[NetflixLike Helper] monitor.run: Error logging 'Service stopped': {e}", xbmc.LOGERROR)