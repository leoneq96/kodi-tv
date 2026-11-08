# -*- coding: utf-8 -*-
# Module: kodi library provider
# Author: NetflixLike Project
# License: GPL v3.0

import xbmc
import json
import time
from resources.lib.kodiutils import log


class KodiLibraryProvider:
    """Provides access to Kodi's video library for widgets."""

    def __init__(self):
        pass

    def _execute_jsonrpc(self, method, params=None):
        """Execute JSON-RPC call to Kodi."""
        try:
            import json
            payload = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params or {},
                "id": 1
            }
            result = xbmc.executeJSONRPC(json.dumps(payload))
            return json.loads(result)
        except Exception as e:
            log(f"JSON-RPC error: {e}")
            return None

    def get_recently_added_movies(self, limit=20):
        """Get recently added movies."""
        result = self._execute_jsonrpc("VideoLibrary.GetMovies", {
            "properties": ["title", "year", "art", "plot", "genre", "rating", "playcount", "lastplayed", "resume"],
            "sort": {"order": "descending", "method": "dateadded"},
            "limits": {"end": limit}
        })
        if result and 'result' in result and 'movies' in result['result']:
            return result['result']['movies']
        return []

    def get_recently_added_episodes(self, limit=20):
        """Get recently added episodes."""
        result = self._execute_jsonrpc("VideoLibrary.GetEpisodes", {
            "properties": ["title", "showtitle", "season", "episode", "art", "plot", "rating", "playcount", "lastplayed", "resume", "firstaired"],
            "sort": {"order": "descending", "method": "dateadded"},
            "limits": {"end": limit}
        })
        if result and 'result' in result and 'episodes' in result['result']:
            return result['result']['episodes']
        return []

    def get_continue_watching_movies(self, limit=20):
        """Get movies with resume position."""
        result = self._execute_jsonrpc("VideoLibrary.GetMovies", {
            "properties": ["title", "year", "art", "plot", "rating", "playcount", "lastplayed", "resume"],
            "sort": {"order": "descending", "method": "lastplayed"},
            "limits": {"end": limit * 3}  # Get more to filter
        })
        if result and 'result' in result and 'movies' in result['result']:
            movies = []
            for movie in result['result']['movies']:
                resume = movie.get('resume', {})
                if resume.get('position', 0) > 0:
                    movie['resume'] = resume
                    yield movie
                    # Limit after filtering
                    if len(list(result)) >= limit:
                        break
        return []

    def get_continue_watching_episodes(self, limit=20):
        """Get episodes with resume position."""
        result = self._execute_jsonrpc("VideoLibrary.GetEpisodes", {
            "properties": ["title", "showtitle", "season", "episode", "art", "plot", "rating", "playcount", "lastplayed", "resume", "firstaired"],
            "sort": {"order": "descending", "method": "lastplayed"},
            "limits": {"end": limit * 3}
        })
        if result and 'result' in result and 'episodes' in result['result']:
            for ep in result['result']['episodes']:
                resume = ep.get('resume', {})
                if resume.get('position', 0) > 0:
                    yield ep

    def get_recently_watched(self, limit=20):
        """Get recently watched items (movies and episodes combined)."""
        items = []
        for movie in self.get_continue_watching_movies(limit):
            movie['_type'] = 'movie'
            items.append(movie)
        for ep in self.get_continue_watching_episodes(limit):
            ep['_type'] = 'episode'
            items.append(ep)

        # Sort by last played
        items.sort(key=lambda x: x.get('lastplayed', ''), reverse=True)
        return items[:limit]

    def get_in_progress_tvshows(self, limit=20):
        """Get TV shows with in-progress episodes."""
        result = self._execute_jsonrpc("VideoLibrary.GetTVShows", {
            "properties": ["title", "art", "genre", "rating", "playcount", "watchedepisodes", "episode", "lastplayed"],
            "sort": {"order": "descending", "method": "lastplayed"},
            "limits": {"end": limit}
        })
        if result and 'result' in result and 'tvshows' in result['result']:
            shows = []
            for show in result['result']['tvshows']:
                if show.get('watchedepisodes', 0) > 0 and show.get('watchedepisodes', 0) < show.get('episode', 0):
                    yield show
        return []

    def get_in_progress_movies(self, limit=20):
        """Get movies with partial progress."""
        result = self._execute_jsonrpc("VideoLibrary.GetMovies", {
            "properties": ["title", "year", "art", "plot", "rating", "playcount", "lastplayed", "resume"],
            "sort": {"order": "descending", "method": "lastplayed"},
            "limits": {"end": limit * 3}
        })
        if result and 'result' in result and 'movies' in result['result']:
            for movie in result['result']['movies']:
                resume = movie.get('resume', {})
                if 0 < resume.get('position', 0) < resume.get('total', 1):
                    yield movie

    def get_all_continue_watching(self, limit=20):
        """Get all continue watching items combined."""
        items = []

        # Movies in progress
        for movie in self.get_in_progress_movies(limit):
            movie['_type'] = 'movie'
            movie['_source'] = 'kodi'
            yield movie

        # Episodes in progress
        for ep in self.get_continue_watching_episodes(limit):
            ep['_type'] = 'episode'
            ep['_source'] = 'kodi'
            yield ep

        # Recently added as fallback
        if limit:
            recent_movies = self.get_recently_added_movies(5)
            for m in recent_movies:
                m['_type'] = 'movie'
                m['_source'] = 'kodi_recent'
                yield m

            recent_eps = self.get_recently_added_episodes(5)
            for ep in recent_eps:
                ep['_type'] = 'episode'
                ep['_source'] = 'kodi_recent'
                yield ep