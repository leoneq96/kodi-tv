# -*- coding: utf-8 -*-
# Module: fanfilm provider
# Author: NetflixLike Project
# License: GPL v3.0

import xbmc
import xbmcgui
import json
import time
from kodiutils import log


class FanFilmProvider:
    """Provides access to FanFilm data for widgets."""

    def __init__(self):
        self.base_url = 'plugin://plugin.video.fanfilm/'

    def get_popular_movies(self, limit=20):
        """Get popular movies from FanFilm."""
        # This would use FanFilm's internal API
        # For now, return the URL that skin can use directly
        return f"plugin://plugin.video.fanfilm/movie/popular"

    def get_trending_movies(self, limit=20):
        """Get trending movies from FanFilm."""
        return "plugin://plugin.video.fanfilm/movie/trending"

    def get_new_movies(self, limit=20):
        """Get new movies from FanFilm."""
        return "plugin://plugin.video.fanfilm/movie/new"

    def get_popular_tvshows(self, limit=20):
        """Get popular TV shows from FanFilm."""
        return "plugin://plugin.video.fanfilm/show/popular"

    def get_trending_tvshows(self, limit=20):
        """Get trending TV shows from FanFilm."""
        return "plugin://plugin.video.fanfilm/show/trending"

    def get_new_tvshows(self, limit=20):
        """Get new TV shows from FanFilm."""
        return "plugin://plugin.video.fanfilm/show/premiere"

    def get_continue_watching_movies(self):
        """Get continue watching movies from FanFilm."""
        return "plugin://plugin.video.fanfilm/movie/resume"

    def get_continue_watching_tvshows(self):
        """Get continue watching TV shows from FanFilm."""
        return "plugin://plugin.video.fanfilm/show/resume"

    def get_next_up_episodes(self):
        """Get next up episodes from FanFilm."""
        return "plugin://plugin.video.fanfilm/show/next_up"

    def get_history_movies(self):
        """Get movie history from FanFilm."""
        return "plugin://plugin.video.fanfilm/history/movie"

    def get_history_tvshows(self, limit=20):
        """Get TV show history from FanFilm."""
        return "plugin://plugin.video.fanfilm/history/show"

    def get_continue_watching(self, limit=None):
        """Get combined continue watching from FanFilm."""
        # This would need to call FanFilm's internal API
        # For now, return the URLs that skin can use
        return {
            'movies': "plugin://plugin.video.fanfilm/movie/resume",
            'tvshows': "plugin://plugin.video.fanfilm/show/resume"
        }

    def search(self, query, mediatype='multi'):
        """Search FanFilm."""
        if mediatype == 'movie':
            return f"plugin://plugin.video.fanfilm/movie/search/ext?query={query}"
        elif mediatype == 'tvshow':
            return f"plugin://plugin.video.fanfilm/show/search/ext?query={query}"
        else:
            return f"plugin://plugin.video.fanfilm/multi/search/ext?query={query}"

    def get_movie_details(self, tmdb_id):
        """Get movie details."""
        return f"plugin://plugin.video.fanfilm/movie/{tmdb_id}/info"

    def get_tvshow_details(self, tmdb_id):
        """Get TV show details."""
        return f"plugin://plugin.video.fanfilm/show/{tmdb_id}"

    def play_movie(self, tmdb_id):
        """Play movie."""
        return f"plugin://plugin.video.fanfilm/play/movie/{tmdb_id}"

    def play_episode(self, tmdb_id, season, episode):
        """Play TV show episode."""
        return f"plugin://plugin.video.fanfilm/play/show/{tmdb_id}/{season}/{episode}"


class FanFilmHistoryProvider:
    """Provides access to FanFilm's watch history."""

    def __init__(self):
        pass

    def get_movie_history(self, limit=20):
        """Get movie watch history from FanFilm."""
        return "plugin://plugin.video.fanfilm/history/movie"

    def get_tvshow_history(self, limit=20):
        """Get TV show history from FanFilm."""
        return "plugin://plugin.video.fanfilm/history/show"