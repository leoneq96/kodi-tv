# -*- coding: utf-8 -*-
# Module: profiles
# Author: NetflixLike Project
# License: GPL v3.0

import xbmc
import xbmcgui
import xbmcvfs
import json
import time
from resources.lib.kodiutils import log
from resources.lib.database import Database


class ProfileManager:
    """Manages Kodi profiles for Netflix-style profile selection."""

    def __init__(self):
        self.db = Database()
        self.db.init()
        self.current_profile = self.get_active_profile()

    def get_active_profile(self):
        """Get currently active Kodi profile name."""
        return xbmc.getInfoLabel('System.ProfileName')

    def get_profiles(self):
        """Get list of all Kodi profiles with NetflixLike data."""
        profiles = []

        # Get Kodi profiles via JSON-RPC
        try:
            import xbmc
            result = xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Profiles.GetProfiles","params":{"properties":["thumbnail","lockmode"]},"id":1}')
            import json
            result = json.loads(result)
            if 'result' in result and 'profiles' in result['result']:
                for profile in result['result']['profiles']:
                    profiles.append({
                        'name': profile['label'],
                        'thumbnail': profile.get('thumbnail', ''),
                        'lockmode': profile.get('lockmode', 0),
                        'is_active': profile['label'] == self.get_active_profile()
                    })
        except Exception as e:
            log(f"Error getting profiles via JSON-RPC: {e}")
            # Fallback: use local database
            db = Database()
            db.init()
            for row in db.profile_get_all():
                profiles.append({
                    'name': row['name'],
                    'thumbnail': row.get('thumbnail', ''),
                    'is_active': bool(row['is_active'])
                })

        return profiles

    def switch_profile(self, name):
        """Switch to specified profile."""
        if xbmcgui.Dialog().yesno('Zmień profil', f'Przełączyć na profil "{name}"?'):
            xbmc.executebuiltin(f'LoadProfile({name})')
            return True
        return False

    def add_profile(self, name):
        """Add new profile via Kodi's profile manager."""
        xbmc.executebuiltin('ActivateWindow(Profiles)')
        return True