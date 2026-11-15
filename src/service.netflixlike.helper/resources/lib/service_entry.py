# -*- coding: utf-8 -*-
# Module: service_entry
# Author: NetflixLike Project
# License: GPL v3.0

"""
Service entry point for NetflixLike Helper.
This is called by Kodi's CServiceAddonManager when starting the service.
"""

import xbmc
import traceback

try:
    from monitor import NetflixLikeMonitor

    xbmc.log("[NetflixLike Helper] service_entry: Creating monitor instance", xbmc.LOGINFO)
    monitor = NetflixLikeMonitor()
    xbmc.log("[NetflixLike Helper] service_entry: Starting monitor.run()", xbmc.LOGINFO)
    
    # Start the monitor
    monitor.run()
    xbmc.log("[NetflixLike Helper] service_entry: monitor.run() returned", xbmc.LOGINFO)
except Exception as e:
    xbmc.log(f"[NetflixLike Helper] Fatal error in service_entry: {e}", xbmc.LOGFATAL)
    xbmc.log(f"[NetflixLike Helper] Traceback: {traceback.format_exc()}", xbmc.LOGFATAL)