# -*- coding: utf-8 -*-
# Module: service_entry
# Author: NetflixLike Project
# License: GPL v3.0

"""
Service entry point for NetflixLike Helper.
This is called by Kodi's CServiceAddonManager when starting the service.
"""

from monitor import NetflixLikeMonitor

# Start the monitor
NetflixLikeMonitor().run()