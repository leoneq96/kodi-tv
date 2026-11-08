# -*- coding: utf-8 -*-
# Module: mylist
# Author: NetflixLike Project
# License: GPL v3.0

import xbmc
import xbmcgui
import xbmcvfs
import json
import time
from kodiutils import log
from database import Database


class MyList:
    """Manages user's custom list (Moja Lista)."""

    def __init__(self, data=None):
        self.db = Database()
        self.db.init()

    def add_item(self, item):
        """Add item to My List."""
        if not item.get('ffid'):
            return False

        data = item.get('data')
        if isinstance(data, dict):
            import json
            data = json.dumps(data)

        return self.db.mylist_add(
            ffid=item['ffid'],
            title=item.get('title', ''),
            mediatype=item.get('mediatype', 'movie'),
            data=None  # We'll store as None for simplicity
        )

    def remove_item(self, ffid):
        """Remove item from My List."""
        return self.db.mylist_remove(ffid)

    def get_items(self, limit=None):
        """Get all items from My List."""
        db_items = self.db.mylist_get_all(limit=limit)
        items = []

        for row in db_items:
            # Get item info from Kodi library or FanFilm
            item = {
                'label': row['title'] or f"Item {row['ffid']}",
                'path': f'plugin://plugin.video.fanfilm/play/{row["mediatype"]}/{row["ffid"]}',
                'icon': 'DefaultVideo.png',
                'art': {'icon': 'DefaultVideo.png', 'thumb': 'DefaultVideo.png'},
                'info': {
                    'title': row['title'] or f'Item {row["ffid"]}',
                    'mediatype': row['mediatype']
                },
                'ffid': row['ffid'],
                'mediatype': row['mediatype'],
                'is_folder': False
            }
            yield item

    def get_items_list(self, limit=None):
        """Get all items as list."""
        return list(self.get_items(limit))