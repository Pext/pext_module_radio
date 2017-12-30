# RadioBrowser module for Pext
This module allows [Pext](https://github.com/Pext/Pext) to browse 
[RadioBrowser](http://www.radio-browser.info/), tune into and vote for 
internet radio stations listed on it.

# Supported flags
- baseUrl: Use a custom API base Url (default: http://www.radio-browser.info/webservice)
- useragent: Use a custom User Agent (default: Pext RadioBrowser/Development)

# Dependencies
## Debian

    sudo apt-get install python3 ffmpeg

## Fedora
*Note: ffmpeg is not in the default Fedora repositories due to patent concerns*

    sudo dnf install python3 ffmpeg

## macOS

    brew install ffmpeg --with-sdl2

# License
GPLv3+.
