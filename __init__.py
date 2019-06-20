#!/usr/bin/env python3

# Copyright (C) 2016 - 2017 Sylvia van Os <sylvia@hackerchick.me>
#
# Pext RadioBrowser module is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gettext
import html
import json
import os
import time
from shutil import which
from signal import SIGTERM
from subprocess import Popen
from urllib.request import Request, urlopen
from urllib.error import URLError

from pext_base import ModuleBase
from pext_helpers import Action, SelectionType


class Module(ModuleBase):
    def init(self, settings, q):
        self.module_path = os.path.dirname(os.path.abspath(__file__))

        try:
            lang = gettext.translation('pext_module_radio', localedir=os.path.join(self.module_path, 'locale'), languages=[settings['_locale']])
        except FileNotFoundError:
            lang = gettext.NullTranslations()
            print("No {} translation available for pext_module_radio".format(settings['_locale']))

        lang.install()

        self.baseUrl = 'http://www.radio-browser.info/webservice' if ('baseurl' not in settings) else settings['baseurl']

        self.useragent = 'Pext RadioBrowser/Development' if ('useragent' not in settings) else settings['useragent']

        self.settings = settings
        self.q = q

        self.favourites = []
        try:
            with open(os.path.join(self.module_path, "_user_favourites.txt"), "r") as favourites_file:
                for favourite in favourites_file:
                    self.favourites.append(favourite)
        except IOError:
            pass

        self.cached = {'countries': {'time': 0},
                       'codecs': {'time': 0},
                       'languages': {'time': 0},
                       'tags': {'time': 0}}

        self.cachedStations = {'_favourites': {'time': 0},
                               'countries': {},
                               'codecs': {},
                               'languages': {},
                               'tags': {},
                               'topvote': {'time': 0},
                               'topclick': {'time': 0},
                               'lastclick': {'time': 0},
                               'lastchange': {'time': 0}}

        self.nowPlaying = None

        if not which("ffplay"):
            self.q.put([Action.critical_error, _("ffplay is not installed, please install it.")])
            return

        self._get_entries()

    def _cache_expired(self, cache):
        return cache['time'] < time.time() - 600

    def _request_data(self, path, version=1):
        path = path.replace(" ", "%20")

        if version == 1:
            url = '{}/json/{}'.format(self.baseUrl, path)
        else:
            url = '{}/v{}/json/{}'.format(self.baseUrl, version, path)

        request = Request(url,
                          data=None,
                          headers={'User-Agent': self.useragent})

        response = urlopen(request).read().decode('utf-8')
        data = json.loads(response)

        return data

    def _entry_depth(self, text):
        if self._menu_to_type(text) in self.cached:
            return 2
        else:
            return 1

    def _menu_to_type(self, text):
        if text == _('Favourites'):
            return '_favourites'
        elif text == _('By Country'):
            return 'countries'
        elif text == _('By Codec'):
            return 'codecs'
        elif text == _('By Language'):
            return 'languages'
        elif text == _('By Tags'):
            return 'tags'
        elif text == _('By Votes'):
            return 'topvote'
        elif text == _('By Most Tune-Ins'):
            return 'topclick'
        elif text == _('By Most Recent Listener'):
            return 'lastclick'
        elif text == _('By Most Recent Change'):
            return 'lastchange'
        else:
            raise ValueError("Invalid text")

    def _type_to_stations(self, byType):
        if byType == '_favourites':
            return '_favourites'
        elif byType == 'countries':
            return 'stations/bycountryexact'
        elif byType == 'codecs':
            return 'stations/bycodecexact'
        elif byType == 'languages':
            return 'stations/bylanguageexact'
        elif byType == 'tags':
            return 'stations/bytagexact'
        elif byType == 'topvote':
            return 'stations/topvote'
        elif byType == 'topclick':
            return 'stations/topclick'
        elif byType == 'lastclick':
            return 'stations/lastclick'
        elif byType == 'lastchange':
            return 'stations/lastchange'
        else:
            raise ValueError("Invalid type")

    def _get_entries(self):
        if (self.favourites):
            self.q.put([Action.add_entry, _('Favourites')])
        self.q.put([Action.add_entry, _('By Country')])
        self.q.put([Action.add_entry, _('By Codec')])
        self.q.put([Action.add_entry, _('By Language')])
        self.q.put([Action.add_entry, _('By Tags')])
        self.q.put([Action.add_entry, _('By Votes')])
        self.q.put([Action.add_entry, _('By Most Tune-Ins')])
        self.q.put([Action.add_entry, _('By Most Recent Listener')])
        self.q.put([Action.add_entry, _('By Most Recent Change')])
        if self.settings['_api_version'] < [0, 11, 0] and self.nowPlaying:
            if self.nowPlaying['process']:
                self.q.put([Action.add_command, _('mute')])
            else:
                self.q.put([Action.add_command, _('unmute')])

            self.q.put([Action.add_command, _('stop')])
            self.q.put([Action.add_command, _('vote')])

    def _get_list(self, path):
        self.q.put([Action.replace_entry_list, []])

        if self._cache_expired(self.cached[path]):
            self.cached[path] = {'time': time.time(), 'data': self._request_data(path)}

        for entry in self.cached[path]['data']:
            self.q.put([Action.add_entry, _('{} ({} stations)').format(entry['name'], entry['stationcount'])])

    def _get_stations(self, byType, searchTerm):
        self.q.put([Action.replace_entry_list, []])

        if byType == '_favourites':
            if self._cache_expired(self.cachedStations[byType]):
                data = []
                for favourite in self.favourites:
                    station_data = self._request_data('stations/byid/{}'.format(favourite))
                    if station_data:
                        data.append(station_data[0])

                self.cachedStations[byType] = {'time': time.time(), 'data': data}
            cache = self.cachedStations[byType]

        else:
            if searchTerm:
                if not searchTerm in self.cachedStations[byType] or self._cache_expired(self.cachedStations[byType][searchTerm]):
                    self.cachedStations[byType][searchTerm] = {'time': time.time(), 'data': self._request_data('{}/{}'.format(self._type_to_stations(byType), searchTerm))}

                cache = self.cachedStations[byType][searchTerm]
            else:
                if self._cache_expired(self.cachedStations[byType]):
                    self.cachedStations[byType] = {'time': time.time(), 'data': self._request_data(self._type_to_stations(byType))}

                cache = self.cachedStations[byType]

        for entry in cache['data']:
            self.q.put([Action.add_entry, entry['name']])
            if self.settings['_api_version'] >= [0, 3, 1]:
                self.q.put([Action.set_entry_info, entry['name'], _("<b>{}</b><br/><br/><b>Bitrate: </b>{} kbps<br/><b>Codec: </b>{}<br/><b>Language: </b>{}<br/><b>Location: </b>{}<br/><b>Tags: </b>{}<br/><b>Homepage: </b><a href='{}'>{}</a>").format(html.escape(entry['name']), html.escape(entry['bitrate']), html.escape(entry['codec']), html.escape(entry['language']), "{}, {}".format(html.escape(entry['state']), html.escape(entry['country'])) if entry['state'] else html.escape(entry['country']), html.escape(", ".join(entry['tags'].split(",")) if entry['tags'] else "None"), html.escape(entry['homepage']), html.escape(entry['homepage']))])

    def _play_station(self, byType, searchTerm, stationName):
        self._stop_playing()

        if searchTerm:
            cache = self.cachedStations[byType][searchTerm]
        else:
            cache = self.cachedStations[byType]

        for station in cache['data']:
            if station['name'] == stationName:
                station_id = station['id']
                station_info = station
                break

        response = self._request_data('url/{}'.format(station_id), version=2)

        if response['ok'] == 'false':
            self.q.put([Action.add_error, response['message']])
            return False

        # TODO: Replace ffplay with something more easily scriptable that
        # preferrably notifies us of song changes on the station.
        self.nowPlaying = {'id': station_id,
                           'name': stationName,
                           'url': response['url'],
                           'process': None}

        if self.settings['_api_version'] >= [0, 6, 0]:
            self.q.put([Action.set_base_info, _("<b>Tuned into:</b><br/>{}<br/><br/><b>Bitrate: </b>{} kbps<br/><b>Codec: </b>{}<br/><b>Language: </b>{}<br/><b>Location: </b>{}<br/><b>Tags: </b>{}<br/><b>Homepage: </b><a href='{}'>{}</a>").format(html.escape(station_info['name']), html.escape(station_info['bitrate']), html.escape(station_info['codec']), html.escape(station_info['language']), "{}, {}".format(html.escape(station_info['state']), html.escape(station_info['country'])) if station_info['state'] else html.escape(station_info['country']), html.escape(", ".join(station_info['tags'].split(",")) if station_info['tags'] else "None"), html.escape(station_info['homepage']), html.escape(station_info['homepage']))])

        self._toggle_mute()

        return True

    def _toggle_mute(self):
        """Toggle mute.

        While this function technically disconnects or connects to the
        station, instead of just muting, it is simpler code-wise and has
        the added benefit of saving bandwidth.

        TODO: Replace this with an actual mute function.
        """
        if self.nowPlaying:
            if self.nowPlaying['process']:
                os.kill(self.nowPlaying['process'].pid, SIGTERM)
                self.nowPlaying['process'] = None
                self.q.put([Action.set_header, _('Tuned into {} (muted)').format(self.nowPlaying['name'])])
                if self.settings['_api_version'] >= [0, 6, 0]:
                    self.q.put([Action.set_base_context, [_("Unmute"), _("Stop"), _("Favourite"), _("Vote up")]])
            else:
                self.q.put([Action.set_header, _('Tuned into {}').format(self.nowPlaying['name'])])
                self.nowPlaying['process'] = Popen(['ffplay',
                                                    '-nodisp',
                                                    '-nostats',
                                                    '-loglevel', '0',
                                                    self.nowPlaying['url']])
                if self.settings['_api_version'] >= [0, 6, 0]:
                    self.q.put([Action.set_base_context, [_("Mute"), _("Stop"), _("Favourite"), _("Vote up")]])

    def _stop_playing(self):
        if self.nowPlaying:
            if self.nowPlaying['process']:
                os.kill(self.nowPlaying['process'].pid, SIGTERM)
            self.nowPlaying = None
            self.q.put([Action.set_header])
            if self.settings['_api_version'] >= [0, 6, 0]:
                self.q.put([Action.set_base_info])
                self.q.put([Action.set_base_context])

    def _add_to_favourites(self, station_id):
        with open(os.path.join(self.module_path, "_user_favourites.txt"), "a") as favourites_file:
            favourites_file.write('{}\n'.format(station_id))
            self.favourites.append(station_id)
            self.cachedStations['_favourites'] = {'time': 0}

    def _vote_station(self):
        result = self._request_data('vote/{}'.format(self.nowPlaying['id']))
        if result['ok'] == "true":
            self.q.put([Action.add_message, _('Voted for station {}').format(self.nowPlaying['name'])])
        else:
            self.q.put([Action.add_error, _('Failed to vote for {}: {}').format(self.nowPlaying['name'], result['message'])])

    def stop(self):
        self._stop_playing()

    def selection_made(self, selection):
        if self.settings['_api_version'] >= [0, 6, 0] and len(selection) > 0 and selection[-1]['type'] == SelectionType.none:
            if selection[-1]['context_option'] in [_('Mute'), _('Unmute')]:
                self._toggle_mute()
            elif selection[-1]['context_option'] == _('Stop'):
                self._stop_playing()
            elif selection[-1]['context_option'] == _('Favourite'):
                self._add_to_favourites(self.nowPlaying['id'])
            elif selection[-1]['context_option'] == _('Vote up'):
                 self._vote_station()
            self.q.put([Action.set_selection, selection[:-1]])
            return

        self.q.put([Action.replace_command_list, []])
        if len(selection) == 0:
            self.q.put([Action.replace_entry_list, []])
            self._get_entries()
        elif len(selection) == 1:
            # Force station list when no subcategories
            if self._entry_depth(selection[0]['value']) == 1:
                self._get_stations(self._menu_to_type(selection[0]['value']), '')
                return

            menuText = selection[0]['value']
            self._get_list(self._menu_to_type(menuText))
        elif len(selection) == 2:
            # Force playing when no subcategories
            if self._entry_depth(selection[0]['value']) == 1:
                if self._play_station(self._menu_to_type(selection[0]['value']), '', selection[1]['value']):
                    self.q.put([Action.close])
                else:
                    self.q.put([Action.set_selection, selection[:-1]])

                return

            # Remove station count from searchterm
            searchTerm = selection[1]['value'][:selection[1]['value'].rfind('(')].rstrip()

            self._get_stations(self._menu_to_type(selection[0]['value']), searchTerm)
        elif len(selection) == 3:
            # Remove station count from searchterm
            searchTerm = selection[1]['value'][:selection[1]['value'].rfind('(')].rstrip()

            if self._play_station(self._menu_to_type(selection[0]['value']), searchTerm, selection[2]['value']):
                self.q.put([Action.close])
            else:
                self.q.put([Action.set_selection, selection[:-1]])
        else:
            self.q.put([Action.critical_error, _('Unexpected selection_made value: {}').format(selection)])

    def process_response(self, response):
        pass
