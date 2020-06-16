#!/usr/bin/env python3

# Copyright (C) 2016 - 2018 Sylvia van Os <sylvia@hackerchick.me>
#
# Pext radio module is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
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
import json
import os

languages = [dirname for dirname in os.listdir(os.path.join('.', 'locale')) if os.path.isdir(os.path.join('.', 'locale', dirname))] + [None]

for language in languages:
    if not language:
        lang = gettext.NullTranslations()
    else:
        try:
            lang = gettext.translation('pext_module_radio', localedir=os.path.join('.', 'locale'), languages=[language])
        except FileNotFoundError:
            lang = gettext.NullTranslations()
            print("No {} metadata translation available for pext_module_radio".format(language))
            continue

    lang.install()
    
    filename = 'metadata_{}.json'.format(language) if language else 'metadata.json'
    metadata_file = open(filename, 'w')
    json.dump({'id': 'pext.module.radio',
               'name': _('Radio'),
               'developer': 'Sylvia van Os',
               'description': _('Allows Pext to play internet radio'),
               'homepage': 'https://pext.hackerchick.me/',
               'license': 'GPL-3.0+',
               'git_urls': ['https://github.com/Pext/pext_module_radio'],
               'git_branch_stable': 'stable',
               'bugtracker': 'https://github.com/Pext/pext_module_radio',
               'bugtracker_type': 'github',
               'settings': [{'name': 'baseUrl',
                             'description': _('API base URL'),
                             'defaults': 'http://www.radio-browser.info/webservice'
                            }, {
                             'name': 'useragent',
                             'description': _('User Agent'),
                             'default': 'Pext RadioBrowser/Development'
                            }],
               'platforms': ['Linux', 'Darwin']},
              metadata_file, indent=2, sort_keys=True)
