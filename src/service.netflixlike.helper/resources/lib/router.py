# -*- coding: utf-8 -*-
# Module: router
# Author: NetflixLike Project
# License: GPL v3.0

import re
import xbmc
from functools import wraps


class Router:
    """Simple URL router for Kodi plugin."""

    def __init__(self):
        self.routes = []

    def add_route(self, pattern, handler):
        """Add a route pattern and handler."""
        # Convert pattern to regex
        regex_pattern = '^' + pattern.replace('/', r'\/').replace('<', '(?P<').replace('>', '>[^/]+)') + '$'
        self.routes.append((re.compile(regex_pattern), handler))

    def dispatch(self, path, **kwargs):
        """Dispatch path to appropriate handler."""
        for pattern, handler in self.routes:
            match = pattern.match(path)
            if match:
                params = match.groupdict()
                params.update(kwargs)
                return handler(**params)
        return None