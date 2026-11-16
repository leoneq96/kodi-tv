# -*- coding: utf-8 -*-
# Module: continuewatching
# Author: NetflixLike Project
# License: GPL v3.0

import xbmc
import json
import re
import time
from urllib.parse import unquote
from kodiutils import log
from database import Database
from providers.fanfilm import FanFilmProvider
from providers.kodilibrary import KodiLibraryProvider

# FanFilm dokleja do etykiet znaczniki formatowania i date obejrzenia,
# np. "Stra\u017cnicy Galaktyki vol. 2 [COLOR gray][2026-10-30][/COLOR]".
_LABEL_TAG_RE = re.compile(
    r'\[/?(?:COLOR|FONT)(?:[=\s][^\]]*)?\]'
    r'|\[/?(?:B|I|UPPERCASE|LOWERCASE|CAPITALIZE|LIGHT|CR)\]',
    re.IGNORECASE)
_LABEL_DATE_RE = re.compile(r'\s*\[\s*\d{4}[-.]\d{2}[-.]\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?\s*\]')


# FanFilm wrzuca do plotu "pasek postepu" z samych liter l, np.
# "[B][COLOR darkgreen]llllllllllllllll[/COLOR] 100%[/B]".
_LABEL_PROGRESS_RE = re.compile(r'^\s*l+\s*\d*\s*%?\s*$', re.IGNORECASE | re.MULTILINE)


def _clean_label(text):
    """Czysty tytul: bez [COLOR]/[I]/[B] i bez daty w nawiasach."""
    if not text:
        return ''
    text = _LABEL_TAG_RE.sub('', text)
    text = _LABEL_DATE_RE.sub('', text)
    return ' '.join(text.split())


# Hero pokazuje opis w 3 liniach (800 px, font_mini_plot ~26 px)
# -> ok. 60 znakow na linie, 180 na calosc.
PLOT_MAX_CHARS = 180


def _truncate_plot(text, limit=PLOT_MAX_CHARS):
    """Skraca opis do 3 linii, po calym slowie, z '...' na koncu."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if ' ' in cut:
        cut = cut.rsplit(' ', 1)[0]
    return cut.rstrip(' ,.;:!?—–') + '...'


def _clean_plot(text):
    """Czysty opis: bez tagow, bez paska "llll... 100%" i max 3 linie."""
    if not text:
        return ''
    text = _LABEL_TAG_RE.sub('', text)
    text = _LABEL_PROGRESS_RE.sub('', text)
    return _truncate_plot(' '.join(text.split()))


def _clean_art_url(value):
    """Kodi podaje art jako image://https%3a%2f%2f... - wyciagamy czysty URL."""
    if not value:
        return ''
    if value.startswith('image://'):
        inner = value[len('image://'):]
        if inner.endswith('/'):
            inner = inner[:-1]
        inner = unquote(inner)
        return inner if inner.startswith('http') else value
    return value


def _tmdb_api_key():
    """Klucz TMDb z zainstalowanego TMDb Helpera (nie trzymamy go w repo)."""
    try:
        import importlib.util
        import xbmcvfs
        path = xbmcvfs.translatePath(
            'special://home/addons/plugin.video.themoviedb.helper/'
            'resources/tmdbhelper/lib/api/api_keys/tmdb.py')
        spec = importlib.util.spec_from_file_location('nl_tmdb_keys', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return getattr(module, 'API_KEY', '') or ''
    except Exception:
        return ''


def tmdb_art(tmdb_id, tmdb_type='movie'):
    """Poster i fanart z TMDb po tmdb_id - tylko gdy FanFilm nie zwrocil art."""
    if not tmdb_id:
        return '', ''
    api_key = _tmdb_api_key()
    if not api_key:
        xbmc.log('[NetflixLike Helper] Brak klucza TMDb - pomijam art dla tmdb_id=%s' % tmdb_id,
                 xbmc.LOGWARNING)
        return '', ''
    try:
        import urllib.request
        kind = 'tv' if tmdb_type in ('tv', 'episode', 'show') else 'movie'
        url = 'https://api.themoviedb.org/3/%s/%s?api_key=%s&language=pl-PL' % (kind, tmdb_id, api_key)
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
        poster = ''
        fanart = ''
        if data.get('poster_path'):
            poster = 'https://image.tmdb.org/t/p/w780%s' % data['poster_path']
        if data.get('backdrop_path'):
            fanart = 'https://image.tmdb.org/t/p/w1280%s' % data['backdrop_path']
        return poster, fanart
    except Exception as e:
        xbmc.log('[NetflixLike Helper] TMDb art error (tmdb_id=%s): %s' % (tmdb_id, e),
                 xbmc.LOGWARNING)
        return '', ''


class ContinueWatching:
    """Manages Continue Watching items from Kodi library and FanFilm history."""

    def __init__(self):
        self.db = Database()
        self.db.init()
        self.fanfilm = FanFilmProvider()
        self.kodi_lib = KodiLibraryProvider()

    def get_items(self, limit=None):
        """Get Continue Watching items from Kodi library and FanFilm."""
        # Get from Kodi library (local database)
        kodi_items = self._get_kodi_continue_watching()
        for item in kodi_items:
            yield self._format_item(item, 'kodi')

        # Get from FanFilm history
        fanfilm_items = self._get_fanfilm_continue_watching(limit)
        for item in fanfilm_items:
            formatted = self._format_item(item, 'fanfilm')
            # Bez plakatu nie ma czego pokazac w rzedzie "Kontynuuj ogladanie"
            if not formatted['art'].get('poster'):
                continue
            yield formatted

    def _get_kodi_continue_watching(self):
        """Get continue watching from Kodi video database."""
        import xbmc
        items = []

        try:
            import json
            result = xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"VideoLibrary.GetEpisodes","params":{"properties":["playcount","lastplayed","resume","art","showtitle","season","episode","title","plot"],"sort":{"order":"descending","method":"lastplayed"},"limits":{"end":20}},"id":1}')
            import json
            result = json.loads(result)
            if 'result' in result and 'episodes' in result['result']:
                for ep in result['result']['episodes']:
                    resume = ep.get('resume', {})
                    if resume.get('position', 0) > 0:
                        yield {
                            'type': 'episode',
                            'title': ep.get('title', ''),
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

            result = xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"VideoLibrary.GetMovies","params":{"properties":["playcount","lastplayed","resume","art","title","plot","year"],"sort":{"order":"descending","method":"lastplayed"},"limits":{"end":20}},"id":1}')
            result = json.loads(result)
            if 'result' in result and 'movies' in result['result']:
                for movie in result['result']['movies']:
                    resume = movie.get('resume', {})
                    if resume.get('position', 0) > 0:
                        yield {
                            'type': 'movie',
                            'title': movie.get('title', ''),
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

    # Pola, ktore FanFilm realnie zwraca (sprawdzone przez Files.GetDirectory):
    #  art: {clearlogo, fanart, landscape, poster, thumb} - obrazy TMDb,
    #  uniqueid: {ffid, ffref, imdb, tmdb, tmdb_id},
    #  year, plot, lastplayed, resume.
    # Bez "properties" Kodi zwraca tylko label/file/type - dlatego wczesniej
    # kafelki mialy DefaultVideo.png.
    FANFILM_PROPERTIES = [
        "art", "thumbnail", "uniqueid", "year", "plot", "lastplayed", "resume",
        "title", "season", "episode", "showtitle", "tvshowid", "playcount",
    ]

    def _fetch_fanfilm_directory(self, path):
        """Fetch directory contents from FanFilm plugin via JSON-RPC."""
        import xbmc
        try:
            rpc_call = {
                "jsonrpc": "2.0",
                "method": "Files.GetDirectory",
                "params": {
                    "directory": path,
                    "media": "video",
                    "properties": self.FANFILM_PROPERTIES,
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
        
        # Extract TMDB ID: najpierw z uniqueid (FanFilm podaje tmdb/tmdb_id),
        # potem awaryjnie z URL (format: plugin://plugin.video.fanfilm/play/movie/<id>)
        tmdb_id = 0
        uniqueid = item.get('uniqueid') or {}
        for key in ('tmdb_id', 'tmdb'):
            try:
                if uniqueid.get(key):
                    tmdb_id = int(uniqueid[key])
                    break
            except (TypeError, ValueError):
                continue
        if not tmdb_id and '/play/movie/' in file_path:
            try:
                tmdb_id = int(file_path.split('/play/movie/')[1].split('/')[0])
            except (ValueError, IndexError):
                pass
        elif not tmdb_id and '/play/show/' in file_path:
            try:
                parts = file_path.split('/play/show/')[1].split('/')
                tmdb_id = int(parts[0]) if parts else 0
            except (ValueError, IndexError):
                pass

        if not uniqueid and tmdb_id:
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
                'title': _clean_label(item.get('title') or item.get('label', '')),
                'year': item.get('year', 0),
                'plot': _clean_plot(item.get('plot') or ''),
                'art': item.get('art', {}),
                'thumbnail': item.get('thumbnail', ''),
                'resume': {'position': position, 'total': total},
                'lastplayed': item.get('lastplayed', ''),
                'dbid': tmdb_id,
                'tmdb_id': tmdb_id,
                # FanFilm gra po swoim ffid (np. 100283995), nie po tmdb_id
                'play_path': file_path,
                'ffid': uniqueid.get('ffid', ''),
            }
        else:  # episode
            return {
                'type': 'episode',
                'title': _clean_label(item.get('title') or item.get('label', '')),
                'showtitle': item.get('showtitle', ''),
                'season': item.get('season', 0),
                'episode': item.get('episode', 0),
                'plot': _clean_plot(item.get('plot') or ''),
                'art': item.get('art', {}),
                'thumbnail': item.get('thumbnail', ''),
                'resume': {'position': position, 'total': total},
                'lastplayed': item.get('lastplayed', ''),
                'dbid': item.get('episodeid', 0),
                'tmdb_id': tmdb_id,
                'tvshow_tmdb_id': item.get('tvshowid', 0),
                'play_path': file_path,
                'ffid': uniqueid.get('ffid', ''),
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
            path = item.get('play_path') or f"plugin://plugin.video.fanfilm/play/movie/{play_id}"
            tmdb_type = 'movie'
        else:  # episode
            label = f"{item.get('showtitle', '')} S{item['season']:02d}E{item['episode']:02d}"
            play_id = item.get('tmdb_id', item.get('dbid', 0))
            path = item.get('play_path') or f"plugin://plugin.video.fanfilm/play/show/{play_id}/{item.get('season', 1)}/{item.get('episode', 1)}"
            tmdb_type = 'tv'

        # Art: najpierw to, co zwrocilo zrodlo (FanFilm podaje obrazy TMDb),
        # a gdy brakuje - poster/fanart z TMDb po tmdb_id.
        art = self._resolve_art(item, tmdb_type)

        resume = item.get('resume', {})
        progress = 0
        total_time = 0
        if resume:
            position = resume.get('position', 0)
            total = resume.get('total', 0)
            if total > 0:
                progress = int((position / total) * 100)
                total_time = total

        label_for_display = _clean_label(item.get('label') or item.get('title') or '')

        return {
            'label': label_for_display,
            'path': path,
            'icon': art.get('poster') or art.get('thumb') or '',
            'art': art,
            'info': {
                'title': item.get('title') or label_for_display,
                'plot': _clean_plot(item.get('plot') or ''),
                'mediatype': 'movie' if item['type'] == 'movie' else 'episode',
                'playcount': 1 if (item.get('resume', {}).get('position', 0) >= (item.get('resume', {}).get('total', 1) * 0.9)) else 0,
                'progress': progress,
                'totaltime': total_time
            },
            'is_folder': False,
            'source': source
        }

    def _resolve_art(self, item, tmdb_type='movie'):
        """Zbior poster/thumb/fanart/clearlogo; brakujace uzupelnia z TMDb."""
        raw = item.get('art') or {}
        poster = _clean_art_url(raw.get('poster') or '')
        thumb = _clean_art_url(raw.get('thumb') or '')
        fanart = _clean_art_url(raw.get('fanart') or '')
        clearlogo = _clean_art_url(raw.get('clearlogo') or '')
        if not poster:
            poster = _clean_art_url(item.get('thumbnail') or '') or thumb
        tmdb_id = item.get('tmdb_id') or 0
        if (not poster or not fanart) and tmdb_id:
            tmdb_poster, tmdb_fanart = tmdb_art(tmdb_id, tmdb_type)
            poster = poster or tmdb_poster
            fanart = fanart or tmdb_fanart
        art = {
            'poster': poster,
            'thumb': thumb or poster,
            'fanart': fanart,
            'icon': poster,
        }
        if clearlogo:
            art['clearlogo'] = clearlogo
        return {key: value for key, value in art.items() if value}