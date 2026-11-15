# -*- coding: utf-8 -*-
# Module: continuewatching
# Author: NetflixLike Project
# License: GPL v3.0

import xbmc
import json
import time
from kodiutils import log
from database import Database
from providers.fanfilm import FanFilmProvider
from providers.kodilibrary import KodiLibraryProvider


class ContinueWatching:
    """Manages Continue Watching items from Kodi library and FanFilm history."""

    def __init__(self):
        self.db = Database()
        self.db.init()
        self.fanfilm = FanFilmProvider()
        self.kodi_lib = KodiLibraryProvider()

    def get_items(self, limit=None):
        """Get Continue Watching items from Kodi library and FanFilm."""
        items = []

        # Get from Kodi library (local database)
        kodi_items = self._get_kodi_continue_watching()
        for item in kodi_items:
            yield self._format_item(item, 'kodi')

        # Get from FanFilm history
        fanfilm_items = self._get_fanfilm_continue_watching(limit)
        for item in fanfilm_items:
            yield self._format_item(item, 'fanfilm')

    def _get_kodi_continue_watching(self):
        """Get continue watching from Kodi video database."""
        import xbmc
        items = []

        try:
            import json
            result = xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"VideoLibrary.GetEpisodes","params":{"properties":["playcount","lastplayed","resume","art","showtitle","season","episode"],"sort":{"order":"descending","method":"lastplayed"},"limits":{"end":20}},"id":1}')
            import json
            result = json.loads(result)
            if 'result' in result and 'episodes' in result['result']:
                for ep in result['result']['episodes']:
                    resume = ep.get('resume', {})
                    if resume.get('position', 0) > 0:
                        yield {
                            'type': 'episode',
                            'title': ep.get('label', ''),
                            'showtitle': ep.get('showtitle', ''),
                            'season': ep.get('season', 0),
                            'episode': ep.get('episode', 0),
                            'plot': ep.get('plot', ''),
                            'art': ep.get('art', {}),
                            'resume': resume,
                            'lastplayed': ep.get('lastplayed', ''),
                            'dbid': ep.get('episodeid', 0),
                            'type': 'episode'
                        }

            result = xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"VideoLibrary.GetMovies","params":{"properties":["playcount","lastplayed","resume","art"],"sort":{"order":"descending","method":"lastplayed"},"limits":{"end":20}},"id":1}')
            result = json.loads(result)
            if 'result' in result and 'movies' in result['result']:
                for movie in result['result']['movies']:
                    resume = movie.get('resume', {})
                    if resume.get('position', 0) > 0:
                        yield {
                            'type': 'movie',
                            'title': movie.get('label', ''),
                            'year': movie.get('year', 0),
                            'plot': movie.get('plot', ''),
                            'art': movie.get('art', {}),
                            'resume': resume,
                            'lastplayed': movie.get('lastplayed', ''),
                            'dbid': movie.get('movieid', 0),
                            'type': 'movie'
                        }
        except Exception as e:
            import xbmc
            xbmc.log(f"[NetflixLike] Error getting Kodi continue watching: {e}", xbmc.LOGERROR)

    def _get_fanfilm_continue_watching(self, limit=None):
        """Get continue watching from FanFilm history."""
        # Fetch from FanFilm's history endpoints
        # /history/movie and /history/show
        
        # Get movie history
        movie_history = self._fetch_fanfilm_directory("plugin://plugin.video.fanfilm/history/movie")
        for item in movie_history[:limit] if limit else movie_history:
            # Skip placeholder items
            if item.get('label', '').startswith('Brak treści'):
                continue
            yield self._parse_fanfilm_history_item(item, 'movie')
        
        # Get TV show history
        tvshow_history = self._fetch_fanfilm_directory("plugin://plugin.video.fanfilm/history/show")
        for item in tvshow_history[:limit] if limit else tvshow_history:
            # Skip placeholder items
            if item.get('label', '').startswith('Brak treści'):
                continue
            yield self._parse_fanfilm_history_item(item, 'episode')

    def _fetch_fanfilm_directory(self, path):
        """Fetch directory contents from FanFilm plugin via JSON-RPC."""
        import xbmc
        try:
            # Use Files.GetDirectory to get plugin contents (without properties that FanFilm might not support)
            rpc_call = {
                "jsonrpc": "2.0",
                "method": "Files.GetDirectory",
                "params": {
                    "directory": path,
                    "media": "video"
                },
                "id": 1
            }
            result = xbmc.executeJSONRPC(json.dumps(rpc_call))
            result = json.loads(result)
            
            if 'result' in result and 'files' in result['result']:
                return result['result']['files']
        except Exception as e:
            xbmc.log(f"[NetflixLike Helper] Error fetching FanFilm directory {path}: {e}", xbmc.LOGERROR)
        return []

    def _parse_fanfilm_history_item(self, item, default_type):
        """Parse FanFilm history item to standard format."""
        # Determine type from item properties
        mediatype = item.get('type', default_type)
        
        # Get file path (plugin URL)
        file_path = item.get('file', '')
        
        # Extract TMDB ID from file path
        # Format: plugin://plugin.video.fanfilm/play/movie/{tmdb_id}
        tmdb_id = 0
        if '/play/movie/' in file_path:
            try:
                tmdb_id = int(file_path.split('/play/movie/')[1].split('/')[0])
            except (ValueError, IndexError):
                pass
        elif '/play/show/' in file_path:
            try:
                parts = file_path.split('/play/show/')[1].split('/')
                tmdb_id = int(parts[0]) if parts else 0
            except (ValueError, IndexError):
                pass
        
        # Get unique IDs (tmdb, imdb, etc.) - not available from basic history
        uniqueid = {}
        if tmdb_id:
            uniqueid['tmdb'] = tmdb_id
        
        # Get resume info - not available from basic history
        # Use mock values or try to get from item
        resume = item.get('resume', {})
        position = resume.get('position', 0)
        total = resume.get('total', 0)
        
        # If no resume info, create mock progress (50%)
        if position == 0 and total == 0:
            position = 1
            total = 2
        
        if mediatype == 'movie':
            return {
                'type': 'movie',
                'title': item.get('label', ''),
                'year': item.get('year', 0),
                'plot': item.get('plot', ''),
                'art': item.get('art', {}),
                'resume': {'position': position, 'total': total},
                'lastplayed': item.get('lastplayed', ''),
                'dbid': tmdb_id,
                'type': 'movie',
                'tmdb_id': tmdb_id
            }
        else:  # episode
            return {
                'type': 'episode',
                'title': item.get('label', ''),
                'showtitle': item.get('showtitle', ''),
                'season': item.get('season', 0),
                'episode': item.get('episode', 0),
                'plot': item.get('plot', ''),
                'art': item.get('art', {}),
                'resume': {'position': position, 'total': total},
                'lastplayed': item.get('lastplayed', ''),
                'dbid': item.get('episodeid', 0),
                'type': 'episode',
                'tmdb_id': uniqueid.get('tmdb', 0),
                'tvshow_tmdb_id': item.get('tvshowid', 0)
            }

    def get_items_list(self, limit=None):
        """Get items as list."""
        import itertools
        items = []

        # Get from Kodi
        for item in self._get_kodi_continue_watching():
            if len(items) >= (limit or 100):
                break
            items.append(self._format_item(item, 'kodi'))

        # Get from FanFilm
        for item in self._get_fanfilm_continue_watching(limit):
            if len(items) >= (limit or 100):
                break
            items.append(self._format_item(item, 'fanfilm'))

        return items

    def _format_item(self, item, source):
        """Format item for display."""
        if item['type'] == 'movie':
            label = item['title']
            if item.get('year'):
                label += f" ({item['year']})"
            # Use TMDb ID for FanFilm, dbid for Kodi
            play_id = item.get('tmdb_id', item.get('dbid', 0))
            path = f"plugin://plugin.video.fanfilm/play/movie/{play_id}"
            icon = item.get('art', {}).get('poster', 'DefaultMovie.png')
            fanart = item.get('art', {}).get('fanart', '')
        else:  # episode
            label = f"{item.get('showtitle', '')} S{item['season']:02d}E{item['episode']:02d}"
            play_id = item.get('tmdb_id', item.get('dbid', 0))
            path = f"plugin://plugin.video.fanfilm/play/show/{play_id}/{item.get('season', 1)}/{item.get('episode', 1)}"
            icon = item.get('art', {}).get('thumb', item.get('art', {}).get('poster', 'DefaultEpisode.png'))
            fanart = item.get('art', {}).get('fanart', '')

        resume = item.get('resume', {})
        progress = 0
        total_time = 0
        if resume:
            position = resume.get('position', 0)
            total = resume.get('total', 0)
            if total > 0:
                progress = int((position / total) * 100)
                total_time = total

        return {
            'label': item.get('label', item.get('title', '')),
            'path': path,
            'icon': item.get('art', {}).get('poster', item.get('art', {}).get('thumb', 'DefaultVideo.png')),
            'art': {
                'icon': item.get('art', {}).get('poster', 'DefaultVideo.png'),
                'thumb': item.get('art', {}).get('thumb', 'DefaultVideo.png'),
                'poster': item.get('art', {}).get('poster', 'DefaultVideo.png'),
                'fanart': fanart
            },
            'info': {
                'title': item.get('label', item.get('title', '')),
                'plot': item.get('plot', ''),
                'mediatype': 'movie' if item['type'] == 'movie' else 'episode',
                'playcount': 1 if (item.get('resume', {}).get('position', 0) >= (item.get('resume', {}).get('total', 1) * 0.9)) else 0,
                'progress': progress,
                'totaltime': total_time
            },
            'is_folder': False,
            'source': source
        }