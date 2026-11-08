# -*- coding: utf-8 -*-
# Module: script_entry
# Author: NetflixLike Project
# License: GPL v3.0

"""
Script entry point for NetflixLike Helper.
This is called by Kodi's Python script engine when the script is run.
"""

import xbmc
import xbmcaddon
import xbmcvfs
import json
import os
import sys
import traceback

# Add resources/lib to path
ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
sys.path.insert(0, os.path.join(ADDON_PATH, 'resources', 'lib'))

from resources.lib.service_entry import main

if __name__ == '__main__':
    main()