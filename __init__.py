#!/usr/bin/env python3

# Copyright (C) 2016 - 2019 Sylvia van Os <sylvia@hackerchick.me>
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
import os
import time

from pyradios import RadioBrowser
from shutil import which
from signal import SIGTERM
from subprocess import Popen

from pext_base import ModuleBase
from pext_helpers import Action, SelectionType


class Module(ModuleBase):
    def init(self, settings, q):
        self.module_path = os.path.dirname(os.path.abspath(__file__))

        try:
            lang = gettext.translation('pext_module_radio', localedir=os.path.join(self.module_path, 'locale'),
                                       languages=[settings['_locale']])
        except FileNotFoundError:
            lang = gettext.NullTranslations()
            print("No {} translation available for pext_module_radio".format(settings['_locale']))

        lang.install()

        self.rb = RadioBrowser()

        self.settings = settings
        self.q = q

        self.favourites = []
        try:
            with open(os.path.join(self.module_path, "_user_favourites.txt"), "r") as favourites_file:
                for favourite in favourites_file:
                    self.favourites.append(favourite.strip())
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

    def _get_stations_by_menu_type(self, search_type):
        if search_type == 'countries':
            return self.rb.countries()
        elif search_type == 'codecs':
            return self.rb.codecs()
        elif search_type == 'languages':
            return self.rb.languages()
        elif search_type == 'tags':
            return self.rb.tags()
        else:
            return self._search_stations_by_type(search_type)

    def _search_stations_by_type(self, search_type, search_term=None):
        if search_type == 'countries':
            return self.rb.stations_by_country(search_term, True)
        elif search_type == 'codecs':
            return self.rb.stations_by_codec(search_term, True)
        elif search_type == 'languages':
            return self.rb.stations_by_language(search_term, True)
        elif search_type == 'tags':
            return self.rb.stations_by_tag(search_term, True)
        elif search_type == 'topvote':
            return self.rb.stations(order='votes')
        elif search_type == 'topclick':
            return self.rb.stations(order='clickcount')
        elif search_type == 'lastclick':
            return self.rb.stations(order='clicktimestamp')
        elif search_type == 'lastchange':
            return self.rb.stations(order='lastchangetime')
        else:
            raise ValueError("Invalid type")

    def _get_entries(self):
        if self.favourites:
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
            self.cached[path] = {'time': time.time(), 'data': self._get_stations_by_menu_type(path)}

        for entry in self.cached[path]['data']:
            self.q.put([Action.add_entry, _('{} ({} stations)').format(entry['name'], entry['stationcount'])])

    def _get_stations(self, search_type, search_term):
        if search_type == '_favourites':
            if self._cache_expired(self.cachedStations[search_type]):
                data = []
                for favourite in self.favourites:
                    station_data = self.rb.station_by_uuid(favourite)
                    if station_data:
                        data.append(station_data[0])

                self.cachedStations[search_type] = {'time': time.time(), 'data': data}

            return self.cachedStations[search_type]

        if search_term:
            if search_term not in self.cachedStations[search_type] or self._cache_expired(
                    self.cachedStations[search_type][search_term]):
                self.cachedStations[search_type][search_term] = {'time': time.time(),
                                                                 'data': self._search_stations_by_type(search_type,
                                                                                                       search_term)}

            return self.cachedStations[search_type][search_term]

        if self._cache_expired(self.cachedStations[search_type]):
            self.cachedStations[search_type] = {'time': time.time(), 'data': self._search_stations_by_type(search_type)}

        return self.cachedStations[search_type]

    def _list_stations(self, search_type, search_term):
        self.q.put([Action.replace_entry_list, []])

        cache = self._get_stations(search_type, search_term)

        for entry in cache['data']:
            self.q.put([Action.add_entry, entry['name']])
            if self.settings['_api_version'] >= [0, 3, 1]:
                self.q.put([Action.set_entry_info, entry['name'], _("<b>{}</b><br/><br/><b>Bitrate: </b>{} kbps<br/><b>Codec: </b>{}<br/><b>Language: </b>{}<br/><b>Location: </b>{}<br/><b>Tags: </b>{}<br/><b>Homepage: </b><a href='{}'>{}</a>")
                           .format(html.escape(entry['name']), html.escape(str(entry['bitrate'])), html.escape(entry['codec']), html.escape(entry['language']), "{}, {}".format(html.escape(entry['state']), html.escape(entry['country'])) if entry['state'] else html.escape(entry['country']), html.escape(", ".join(entry['tags'].split(",")) if entry['tags'] else "None"), html.escape(entry['homepage']), html.escape(entry['homepage']))])
            if self.settings['_api_version'] >= [0, 6, 0] and search_type == '_favourites':
                self.q.put([Action.set_entry_context, entry['name'], [_("Unfavourite")]])

    def _play_station(self, byType, searchTerm, stationName):
        self._stop_playing()

        if searchTerm:
            cache = self.cachedStations[byType][searchTerm]
        else:
            cache = self.cachedStations[byType]

        for station in cache['data']:
            if station['name'] == stationName:
                station_uuid = station['stationuuid']
                station_info = station
                break

        response = self.rb.click_counter(station_uuid)

        if response['ok'] == 'false':
            self.q.put([Action.add_error, response['message']])
            return False

        # TODO: Replace ffplay with something more easily scriptable that
        # preferably notifies us of song changes on the station.
        self.nowPlaying = {'id': station_uuid,
                           'name': stationName,
                           'url': response['url'],
                           'process': None}

        if self.settings['_api_version'] >= [0, 6, 0]:
            self.q.put([Action.set_base_info, _("<b>Tuned into:</b><br/>{}<br/><br/><b>Bitrate: </b>{} kbps<br/><b>Codec: </b>{}<br/><b>Language: </b>{}<br/><b>Location: </b>{}<br/><b>Tags: </b>{}<br/><b>Homepage: </b><a href='{}'>{}</a>")
                       .format(html.escape(station_info['name']), html.escape(str(station_info['bitrate'])), html.escape(station_info['codec']), html.escape(station_info['language']), "{}, {}".format(html.escape(station_info['state']), html.escape(station_info['country'])) if station_info['state'] else html.escape(station_info['country']), html.escape(", ".join(station_info['tags'].split(",")) if station_info['tags'] else "None"), html.escape(station_info['homepage']), html.escape(station_info['homepage']))])

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

    def _remove_from_favourites(self, station_name):
        for station in self._get_stations('_favourites', '')['data']:
            if station['name'] == station_name:
                self.favourites.remove(station['stationuuid'])
                with open(os.path.join(self.module_path, "_user_favourites.txt"), "w") as favourites_file:
                    for favourite in self.favourites:
                        favourites_file.write('{}\n'.format(favourite))

                self.cachedStations['_favourites'] = {'time': 0}
                return

        self.q.put([Action.add_error, _('Could not find {} in favourites').format(station_name)])

    def _vote_station(self):
        result = self.rb.client.get('vote/{}'.format(self.nowPlaying['id']))
        if result['ok']:
            self.q.put([Action.add_message, _('Voted for station {}').format(self.nowPlaying['name'])])
        else:
            self.q.put(
                [Action.add_error, _('Failed to vote for {}: {}').format(self.nowPlaying['name'], result['message'])])

    def stop(self):
        self._stop_playing()

    def selection_made(self, selection):
        if self.settings['_api_version'] >= [0, 6, 0] and len(selection) > 0 and selection[-1]['context_option']:
            if selection[-1]['type'] == SelectionType.none:
                if selection[-1]['context_option'] in [_('Mute'), _('Unmute')]:
                    self._toggle_mute()
                elif selection[-1]['context_option'] == _('Stop'):
                    self._stop_playing()
                elif selection[-1]['context_option'] == _('Favourite'):
                    self._add_to_favourites(self.nowPlaying['id'])
                elif selection[-1]['context_option'] == _('Vote up'):
                    self._vote_station()
            elif selection[-1]['context_option'] == _("Unfavourite"):
                self._remove_from_favourites(selection[-1]['value'])
                if not self.favourites:
                    self.q.put([Action.set_selection, []])
                    return

            self.q.put([Action.set_selection, selection[:-1]])
            return

        self.q.put([Action.replace_command_list, []])
        if len(selection) == 0:
            self.q.put([Action.replace_entry_list, []])
            self._get_entries()
        elif len(selection) == 1:
            # Force station list when no subcategories
            if self._entry_depth(selection[0]['value']) == 1:
                self._list_stations(self._menu_to_type(selection[0]['value']), '')
                return

            menu_text = selection[0]['value']
            self._get_list(self._menu_to_type(menu_text))
        elif len(selection) == 2:
            # Force playing when no subcategories
            if self._entry_depth(selection[0]['value']) == 1:
                if self._play_station(self._menu_to_type(selection[0]['value']), '', selection[1]['value']):
                    self.q.put([Action.close])
                else:
                    self.q.put([Action.set_selection, selection[:-1]])

                return

            # Remove station count from search term
            search_term = selection[1]['value'][:selection[1]['value'].rfind('(')].rstrip()

            self._list_stations(self._menu_to_type(selection[0]['value']), search_term)
        elif len(selection) == 3:
            # Remove station count from search term
            search_term = selection[1]['value'][:selection[1]['value'].rfind('(')].rstrip()

            if self._play_station(self._menu_to_type(selection[0]['value']), search_term, selection[2]['value']):
                self.q.put([Action.close])
            else:
                self.q.put([Action.set_selection, selection[:-1]])
        else:
            self.q.put([Action.critical_error, _('Unexpected selection_made value: {}').format(selection)])

    def process_response(self, response):
        pass
