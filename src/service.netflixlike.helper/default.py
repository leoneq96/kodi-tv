# -*- coding: utf-8 -*-
# Module: service.netflixlike.helper
# Author: NetflixLike Project
# License: GPL v3.0

import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs
import json
import os
import time
from urllib.parse import parse_qs, urlparse

from resources.lib.router import Router
from resources.lib.kodiutils import log
from resources.lib.database import Database
from resources.lib.profiles import ProfileManager
from resources.lib.mylist import MyList
from resources.lib.continuewatching import ContinueWatching
from resources.lib.providers.fanfilm import FanFilmProvider
from resources.lib.providers.kodilibrary import KodiLibraryProvider


ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_PATH = ADDON.getAddonInfo('path')
HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]


def get_active_profile():
    return xbmc.getInfoLabel('System.ProfileName')


def get_profile_path():
    profile = get_active_profile()
    addon = xbmcaddon.Addon()
    profile_path = xbmcvfs.translatePath(f"{addon.getAddonInfo('profile')}/{profile}")
    if not xbmcvfs.exists(profile_path):
        xbmcvfs.mkdirs(profile_path)
    return profile_path


def get_data_file():
    return os.path.join(get_profile_path(), 'data.json')


def load_data():
    data_file = get_data_file()
    if xbmcvfs.exists(data_file):
        try:
            content = xbmcvfs.File(data_file, 'r').read()
            return json.loads(content)
        except Exception as e:
            log(f"Error loading data: {e}")
    return {'my_list': [], 'settings': {}}


def save_data(data):
    data_file = get_data_file()
    try:
        xbmcvfs.File(data_file, 'w').write(json.dumps(data, ensure_ascii=False, indent=2))
        return True
    except Exception as e:
        log(f"Error saving data: {e}")
        return False


class PluginRouter:
    def __init__(self):
        self.router = Router()
        self.profile = get_active_profile()
        self.data = {}
        self.mylist = MyList({})
        self.continue_watching = ContinueWatching()
        self.fanfilm = FanFilmProvider()
        self.kodi_lib = KodiLibraryProvider()

        self.router.add_route('/', self.home)
        self.router.add_route('/mylist', self.mylist_view)
        self.router.add_route('/mylist/add', self.mylist_add)
        self.router.add_route('/mylist/remove', self.mylist_remove)
        self.router.add_route('/continue', self.continue_watching_view)
        self.router.add_route('/profiles', self.profiles_view)
        self.router.add_route('/profiles/select', self.profiles_select)
        self.router.add_route('/widget/mylist', self.widget_mylist)
        self.router.add_route('/widget/continue', self.widget_continue)
        self.router.add_route('/widget/profiles', self.widget_profiles)

    def dispatch(self, path, **kwargs):
        parsed = urlparse(path)
        path_only = parsed.path
        query = parse_qs(parsed.query)
        for key, value in query.items():
            if len(value) == 1:
                kwargs[key] = value[0]
        return self.router.dispatch(path, **kwargs)

    def home(self):
        items = [
            {'label': 'Moja Lista', 'path': BASE_URL + '/mylist', 'icon': 'DefaultVideoPlaylists.png', 'is_folder': True},
            {'label': 'Kontynuuj oglądanie', 'path': BASE_URL + '/continue', 'icon': 'DefaultRecentlyAddedMovies.png', 'is_folder': True},
            {'label': 'Profile', 'path': BASE_URL + '/profiles', 'icon': 'DefaultUser.png', 'is_folder': True}
        ]
        self.add_items(items)

    def mylist_view(self):
        items = list(self.mylist.get_items())
        if not items:
            items = [{'label': 'Lista jest pusta', 'path': '', 'icon': 'DefaultVideoPlaylists.png'}]
        self.add_items(items)

    def mylist_add(self, ffid=None, title=None, mediatype=None, **kwargs):
        if not ffid:
            xbmcgui.Dialog().ok('Błąd', 'Brak ID elementu')
            return
        item = {'ffid': ffid, 'title': title or '', 'mediatype': mediatype or 'movie', 'added': int(time.time())}
        if self.mylist.add_item(item):
            xbmcgui.Dialog().notification('NetflixLike', 'Dodano do Mojej Listy', xbmcgui.NOTIFICATION_INFO, 2000)
        else:
            xbmcgui.Dialog().notification('NetflixLike', 'Element już na liście', xbmcgui.NOTIFICATION_INFO, 2000)
        xbmc.executebuiltin('Container.Refresh')

    def mylist_remove(self, ffid=None, **kwargs):
        if not ffid:
            xbmcgui.Dialog().ok('Błąd', 'Brak ID elementu')
            return
        if self.mylist.remove_item(ffid):
            xbmcgui.Dialog().notification('NetflixLike', 'Usunięto z Mojej Listy', xbmcgui.NOTIFICATION_INFO, 2000)
        else:
            xbmcgui.Dialog().notification('NetflixLike', 'Element nie znaleziony', xbmcgui.NOTIFICATION_ERROR, 2000)
        xbmc.executebuiltin('Container.Refresh')

    def continue_watching_view(self):
        items = list(self.continue_watching.get_items(limit=50))
        if not items:
            items = [{'label': 'Brak historii odtwarzania', 'path': '', 'icon': 'DefaultRecentlyAddedMovies.png'}]
        self.add_items(items)

    def profiles_view(self):
        profiles = ProfileManager().get_profiles()
        current = get_active_profile()
        items = []
        for profile in profiles:
            label = profile['name']
            if profile['name'] == current:
                label = f'[B]{label} (aktywny)[/B]'
            items.append({
                'label': label,
                'path': f'{BASE_URL}/profiles/select?name={profile["name"]}',
                'icon': 'DefaultUser.png',
                'is_folder': False,
                'context_menu': [('Ustaw jako aktywny', f'RunPlugin({BASE_URL}/profiles/select?name={profile["name"]})')] if profile['name'] != current else []
            })
        items.append({'label': '[B]+ Dodaj profil[/B]', 'path': f'{BASE_URL}/profiles/add', 'icon': 'DefaultAddSource.png', 'is_folder': False})
        self.add_items(items)

    def profiles_select(self, name=None, **kwargs):
        if name and xbmcgui.Dialog().yesno('Zmień profil', f'Przełączyć na profil "{name}"?'):
            xbmc.executebuiltin(f'LoadProfile({name})')

    def widget_mylist(self):
        items = list(self.mylist.get_items(limit=20))
        self.add_widget_items(items)

    def widget_continue(self):
        items = list(self.continue_watching.get_items(limit=20))
        self.add_widget_items(items)

    def widget_profiles(self):
        profiles = ProfileManager().get_profiles()
        items = []
        for profile in profiles:
            label = profile['name']
            if profile['name'] == get_active_profile():
                label = f'[B]{label} (aktywny)[/B]'
            items.append({'label': label, 'path': f'{BASE_URL}/profiles/select?name={profile["name"]}', 'icon': 'DefaultUser.png'})
        self.add_widget_items(items)

    def add_items(self, items):
        for item in items:
            li = xbmcgui.ListItem(item['label'])
            li.setArt(item.get('art', {'icon': item.get('icon', 'DefaultVideo.png'), 'thumb': item.get('icon', 'DefaultFolder.png')}))
            li.setInfo('video', item.get('info', {'title': item['label']}))
            if item.get('context_menu'):
                li.addContextMenuItems(item['context_menu'])
            path = item.get('path', '')
            is_folder = item.get('is_folder', True)
            xbmcplugin.addDirectoryItem(HANDLE, path, li, is_folder)
        xbmcplugin.endOfDirectory(HANDLE)

    def add_widget_items(self, items):
        for item in items:
            li = xbmcgui.ListItem(item['label'])
            li.setArt(item.get('art', {'icon': item.get('icon', 'DefaultVideo.png'), 'thumb': item.get('icon', 'DefaultVideo.png')}))
            li.setInfo('video', item.get('info', {'title': item['label']}))
            path = item.get('path', '')
            xbmcplugin.addDirectoryItem(HANDLE, path, li, False)
        xbmcplugin.endOfDirectory(HANDLE)


def run_plugin():
    router = PluginRouter()
    router.dispatch(sys.argv[2])


if __name__ == '__main__':
    run_plugin()