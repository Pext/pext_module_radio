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
        self.baseUrl = 'http://www.radio-browser.info/webservice' if ('baseurl' not in settings) else settings['baseurl']

        self.useragent = 'Pext RadioBrowser/Development' if ('useragent' not in settings) else settings['useragent']

        self.q = q

        self.cached = {'countries': {'time': 0},
                       'codecs': {'time': 0},
                       'languages': {'time': 0},
                       'tags': {'time': 0}}

        self.cachedStations = {'countries': {},
                               'codecs': {},
                               'languages': {},
                               'tags': {},
                               'topvote': {'time': 0},
                               'topclick': {'time': 0},
                               'lastclick': {'time': 0},
                               'lastchange': {'time': 0}}

        self.nowPlaying = None

        if not which("ffplay"):
            self.q.put([Action.critical_error, "ffplay is not installed, please install it."])
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
        if text == 'By Country':
            return 'countries'
        elif text == 'By Codec':
            return 'codecs'
        elif text == 'By Language':
            return 'languages'
        elif text == 'By Tags':
            return 'tags'
        elif text == 'By Votes':
            return 'topvote'
        elif text == 'By Most Tune-Ins':
            return 'topclick'
        elif text == 'By Most Recent Listener':
            return 'lastclick'
        elif text == 'By Most Recent Change':
            return 'lastchange'
        else:
            raise ValueError("Invalid text")

    def _type_to_stations(self, byType):
        if byType == 'countries':
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
        self.q.put([Action.add_entry, 'By Country'])
        self.q.put([Action.add_entry, 'By Codec'])
        self.q.put([Action.add_entry, 'By Language'])
        self.q.put([Action.add_entry, 'By Tags'])
        self.q.put([Action.add_entry, 'By Votes'])
        self.q.put([Action.add_entry, 'By Most Tune-Ins'])
        self.q.put([Action.add_entry, 'By Most Recent Listener'])
        self.q.put([Action.add_entry, 'By Most Recent Change'])
        if self.nowPlaying:
            if self.nowPlaying['process']:
                self.q.put([Action.add_command, 'mute'])
            else:
                self.q.put([Action.add_command, 'unmute'])

            self.q.put([Action.add_command, 'stop'])
            self.q.put([Action.add_command, 'vote'])

    def _get_list(self, path):
        self.q.put([Action.replace_entry_list, []])

        if self._cache_expired(self.cached[path]):
            self.cached[path] = {'time': time.time(), 'data': self._request_data(path)}

        for entry in self.cached[path]['data']:
            self.q.put([Action.add_entry, '{} ({} stations)'.format(entry['name'], entry['stationcount'])])

    def _get_stations(self, byType, searchTerm):
        self.q.put([Action.replace_entry_list, []])
        if searchTerm:
            if not searchTerm in self.cachedStations[byType] or self._cache_expired(self.cachedStations[byType][searchTerm]):
                self.cachedStations[byType][searchTerm] = {'time': time.time(), 'data': self._request_data('{}/{}'.format(self._type_to_stations(byType), searchTerm))}

            cache = self.cachedStations[byType][searchTerm]
        else:
            if self._cache_expired(self.cachedStations[byType]):
                self.cachedStations[byType] = {'time': time.time(), 'data': self._request_data(self._type_to_stations(byType))}

            cache = self.cachedStations[byType]

        for entry in cache['data']:
            self.q.put([Action.add_entry, '{} ({}kbps {} - {} - {})'.format(entry['name'], entry['bitrate'], entry['codec'], entry['tags'] if entry['tags'] else 'no tags', entry['homepage'])])

    def _play_station(self, byType, searchTerm, stationName):
        self._stop_playing()

        stationId = None

        if searchTerm:
            cache = self.cachedStations[byType][searchTerm]
        else:
            cache = self.cachedStations[byType]

        for station in cache['data']:
            if station['name'] == stationName:
                stationId = station['id']
                break

        response = self._request_data('url/{}'.format(stationId), version=2)

        if response['ok'] == 'false':
            self.q.put([Action.add_error, response['message']])
            return False

        # TODO: Replace ffplay with something more easily scriptable that
        # preferrably notifies us of song changes on the station.
        self.nowPlaying = {'id': stationId,
                           'name': stationName,
                           'url': response['url'],
                           'process': None}

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
                self.q.put([Action.set_header, 'Tuned into {} (muted)'.format(self.nowPlaying['name'])])
            else:
                self.q.put([Action.set_header, 'Tuned into {}'.format(self.nowPlaying['name'])])
                self.nowPlaying['process'] = Popen(['ffplay',
                                                    '-nodisp',
                                                    '-nostats',
                                                    '-loglevel', '0',
                                                    self.nowPlaying['url']])

    def _stop_playing(self):
        if self.nowPlaying:
            if self.nowPlaying['process']:
                os.kill(self.nowPlaying['process'].pid, SIGTERM)
            self.nowPlaying = None
            self.q.put([Action.set_header])

    def _vote_station(self):
        result = self._request_data('vote/{}'.format(self.nowPlaying['id']))
        if result['ok'] == "true":
            self.q.put([Action.add_message, 'Voted for station {}'.format(self.nowPlaying['name'])])
        else:
            self.q.put([Action.add_error, 'Failed to vote for {}: {}'.format(self.nowPlaying['name'], result['message'])])

    def stop(self):
        self._stop_playing()

    def selection_made(self, selection):
        self.q.put([Action.replace_command_list, []])
        if len(selection) == 0:
            self.q.put([Action.replace_entry_list, []])
            self._get_entries()
        elif len(selection) == 1:
            if selection[0]['type'] == SelectionType.command:
                if selection[0]['value'] in ['mute', 'unmute']:
                    self._toggle_mute()
                elif selection[0]['value'] == 'stop':
                    self._stop_playing()
                elif selection[0]['value'] == 'vote':
                    self._vote_station()

                self.q.put([Action.set_selection, []])
                return

            # Force station list when no subcategories
            if self._entry_depth(selection[0]['value']) == 1:
                self._get_stations(self._menu_to_type(selection[0]['value']), '')
                return

            menuText = selection[0]['value']
            self._get_list(self._menu_to_type(menuText))
        elif len(selection) == 2:
            # Force playing when no subcategories
            if self._entry_depth(selection[0]['value']) == 1:
                # Remove station info from station name
                stationName = selection[1]['value'][:selection[1]['value'].rfind('(')].rstrip()

                if self._play_station(self._menu_to_type(selection[0]['value']), '', stationName):
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

            # Remove station info from station name
            stationName = selection[2]['value'][:selection[2]['value'].rfind('(')].rstrip()

            if self._play_station(self._menu_to_type(selection[0]['value']), searchTerm, stationName):
                self.q.put([Action.close])
            else:
                self.q.put([Action.set_selection, selection[:-1]])
        else:
            self.q.put([Action.critical_error, 'Unexpected selection_made value: {}'.format(selection)])

    def process_response(self, response):
        pass
