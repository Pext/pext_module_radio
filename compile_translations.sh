#!/bin/sh

pygettext2.6.py -d pext_module_radio -a -- *.py

for dir in locale/*/LC_MESSAGES; do
    msgmerge -U -N "$dir/pext_module_radio.po" pext_module_radio.pot
    msgfmt "$dir/pext_module_radio.po" -o "$dir/pext_module_radio.mo"
done

python3 generate_metadata.py

# Copy to names with country code
cp metadata_nl.json metadata_nl_NL.json
cp metadata_es.json metadata_es_ES.json
