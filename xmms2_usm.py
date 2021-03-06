#!/usr/bin/env python
#  XMMS2 - X Music Multiplexer System
#  Copyright (C) 2003-2010 XMMS2 Team
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 2.1 of the License, or (at your option) any later version.
#
#  This library is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#

import numbers
import xmmsclient
import xmmsclient.glib
from xmmsclient.consts import *
from glib import timeout_add_seconds
import os
import sys
import gobject
import dbus
import dbus.service
from sets import Set

#from sound_menu import SoundMenuControls

from dbus.mainloop.glib import DBusGMainLoop
import dbus.mainloop.glib

class XMMS2Playlist(dbus.service.Object):

    def __init__(self, name, description = ""):

        self.name = name
        self.description = description
        self.path = "/org/mpris/MediaPlayer2/xmms2/playlists/%s" % name
        dbus.service.Object.__init__(self, dbus.SessionBus(), self.path)

    def getPlaylist(self):
        return (self.path, self.name, self.description)


class XMMS2USM:

    def __init__(self):
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.ml = gobject.MainLoop()
        #self.ml = gobject.MainLoop(None, False)

        self.xmms = xmmsclient.XMMS("ubuntu-sound-menu")
        try:
            self.xmms.connect(os.getenv("XMMS_PATH"), self.dieme)
        except IOError, detail:
            print "Connection failed:", detail
            sys.exit(1)

        self.conn = xmmsclient.glib.GLibConnector(self.xmms)
        self.confdir = xmmsclient.userconfdir_get()
        self.dbus = DBusGMainLoop(set_as_default=True)
        """self.xmms.playback_current_id(self.my_current_id)"""
        self.xmms.broadcast_playback_status(self.update_playback_status)
        self.xmms.broadcast_playback_current_id(self.update_nowplaying)
        self.xmms.broadcast_playlist_changed(self.signal_update_playlists)
        self.xmms.broadcast_playlist_loaded(self.update_active_playlist)
        self.sound_menu = SoundMenuControls('xmms2')
        self.sound_menu._sound_menu_next = self._sound_menu_next
        self.sound_menu._sound_menu_previous = self._sound_menu_previous
        self.sound_menu._sound_menu_is_playing = self._sound_menu_is_playing
        self.sound_menu._sound_menu_play = self._sound_menu_play
        self.sound_menu._sound_menu_pause = self._sound_menu_pause
        self.sound_menu._sound_menu_raise = self._sound_menu_raise
        self.sound_menu._get_playlists = self._get_playlists
        self.sound_menu._active_playlist = self._active_playlist
        self.sound_menu._activate_playlist = self._activate_playlist

        self.playback_status = False
        self.playlists = []
        self.current_playlist = ""
        timeout_add_seconds(1, self.firstupdate)
        self.ml.run()

    def firstupdate(self):
        self.xmms.playback_status(self.update_playback_status)
        self.xmms.playback_current_id(self.update_nowplaying)
        self.xmms.playlist_current_active(self.update_active_playlist)
        self.xmms.playlist_list(self.update_playlists)

    def dieme(self, etc):
        self.ml.quit()

    def _sound_menu_is_playing(self):
        """return True if the player is currently playing, otherwise, False"""
        return self.playback_status

    def _sound_menu_play(self):
        """start playing if ready"""
        self.xmms.playback_start()

    def _sound_menu_pause(self):
        """pause if playing"""
        self.xmms.playback_pause()

    def _sound_menu_next(self):
        """go to the next song in the list"""
        self.xmms.playlist_set_next_rel(1)
        self.xmms.playback_tickle()

    def _sound_menu_previous(self):
        """go to the previous song in the list"""
        self.xmms.playlist_set_next_rel(-1)
        self.xmms.playback_tickle()


    def _sound_menu_raise(self):
        """raise the window to the top of the z-order"""
        self.xmms.playback_status(self.update_playback_status)
        self.xmms.playback_current_id(self.update_nowplaying)

    def update_playback_status(self, result):
        if result.value() == xmmsclient.PLAYBACK_STATUS_PLAY:
            self.playback_status = True
            self.sound_menu.signal_playing()
        else:
            self.playback_status = False
            self.sound_menu.signal_paused()

    def _get_playlists(self, index=None, maxCount=None, order=None, reverseOrder=None):

        if index is None:
            index = 0
        if maxCount is None:
            maxCount = len(self.playlists)

        playlists = []
        for playlist in self.playlists[index:(maxCount + index)]:
            playlists.append(playlist.getPlaylist())

        if len(playlists) == 0:
            raise Exception("""No playlists available yet""")

        return playlists

    def signal_update_playlists(self, result = None):
        self.update_playlists()

    def update_active_playlist(self, result = None):
        if result == None:
            self.xmms.playlist_current_active(self.update_active_playlist)
        else:
            self.active_playlist = (True, (result.value(), result.value(), ""))
            self.sound_menu._signal_active_playlist()

    def _active_playlist(self):
        return self.active_playlist

    def update_playlists(self, result = None):
        if result == None:
            self.xmms.playlist_list(self.update_playlists)
        else:
            current = Set()
            old = Set()

            for list in result.value():
                if list != "_active":
                    current.add(list)

            for playlist in self.playlists:
                old.add(playlist.name)

            for oldList in (old-current):
                for list in self.playlists:
                    if(list.name == oldList):
                        self.playlists.remove(list)

            for newList in (current-old):
                self.playlists.append(XMMS2Playlist(newList, ""))

            self.sound_menu._signal_playlist_count()


    def activatePlaylistCallback(self, result = None):

        if result != None:
            print result.iserror()
            print result.value()
        else:
            print "Result is none"

    def _activate_playlist(self, playlistpath):
        split = playlistpath.rsplit('/', 2)
        playlist = split[2]
        result = self.xmms.playlist_load(playlist, self.activatePlaylistCallback)
        self.xmms.playlist_current_active(self.update_active_playlist)
        self.xmms.playback_current_id(self.update_nowplaying)

    def update_nowplaying(self, result):
        v = result.value()

        if isinstance(v, numbers.Number):
            # this is the ID. I want the whole info.
            self.xmms.medialib_get_info(result.value(),self.update_nowplaying)
        else:
            if isinstance(v, basestring): # coverart
                info = ""
                #coverimg = StringIO(v)
            elif v is None: # what?
                return
            else:
                info = v

            if not info: return #for "not playing"

            cover = None
            album = None

            if 'album' in info:
                album = info['album'].replace('&', '&amp;').replace('<', '&lt;')

            if 'picture_front' in info:
                cover = "file://" + self.confdir + "/bindata/" + info['picture_front']

            if 'artist' in info and 'title' in info:
                info['artist'] = info['artist'].replace('&', '&amp;').replace('<', '&lt;')
                info['title'] = info['title'].replace('&', '&amp;').replace('<', '&lt;')
                self.sound_menu.song_changed(title = info['title'], artists = info['artist'], cover = cover, album = album)
            elif 'title' in info: #ex. curl
                info['title'] = info['title'].replace('&', '&amp').replace('<', '&lt;')
                self.sound_menu.song_changed(title = info['title'], cover = cover, album = album)
            else:
                info['url'] = info['url'].split('/')[-1].replace('+', ' ')
                self.sound_menu.song_changed(title = info['url'], cover = cover, album = album)

            self.sound_menu.signal_playing()



#!/usr/bin/python
# -*- coding: utf-8 -*-
### BEGIN LICENSE
# Copyright (C) 2011 Rick Spencer <rick.spencer@canonical.com>
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
### END LICENSE

"""Contains SoundMenuControls, A class to make it easy to integrate with the Ubuntu Sound Menu.

In order for a media player to appear in the sonud menu, it must have
a desktop file in /usr/share/applications. For example, for a media player
named "simple" player, there must be desktop file /usr/share/applications/simple-player.desktop

The desktop file must specify that it is indeed a media player. For example, simple-player.desktop
might look like the follwing:
[Desktop Entry]
Name=Simple Player
Comment=SimplePlayer application
Categories=GNOME;Audio;Music;Player;AudioVideo;
Exec=simple-player
Icon=simple-player
Terminal=false
Type=Application
MimeType=application/x-ogg;application/ogg;audio/x-vorbis+ogg;audio/x-scpls;audio/x-mp3;audio/x-mpeg;audio/mpeg;audio/x-mpegurl;audio/x-flac;

In order for the sound menu to run, a dbus loop must be running before
the player is created and before the gtk. mainloop is run. you can add
DBusGMainLoop(set_as_default=True) to your application's __main__ function.

The Ubuntu Sound Menu integrates with applications via the MPRIS2 dbus api,
which is specified here: http://www.mpris.org/2.1/spec/

This module does strive to provide an MPRIS2 implementation, but rather
focuses on the subset of functionality required by the Sound Menu.

The SoundMenuControls class can be ininstatiated, but does not provide any
default functionality. In order to provide the required functionality,
implementations must be provided for the functions starting with
"_sound_menu", such as "_sound_menu_play", etc...

Functions and properties starting with capitalize letters, such as
"Next" and "Previous" are called by the Ubuntu Sound Menu. These
functions and properties are not designed to be called directly
or overriden by application code, only the Sound Menu.

Other functions are designed to be called as needed by the
implementation to inform the Sound Menu of changes. Thse functions
include signal_playing, signal_paused, and song_changed.

Using
#create the sound menu object and reassign functions
sound_menu = SoundMenuControls(desktop_name)
sound_menu._sound_menu_next = _sound_menu_next
sound_menu._sound_menu_previous = _sound_menu_previous
sound_menu._sound_menu_is_playing = _sound_menu_is_playing
sound_menu._sound_menu_play = _sound_menu_play
sound_menu._sound_menu_pause = _sound_menu_play
sound_menu._sound_menu_raise = _sound_menu_raise

#when the song in the player changes, it should inform
the sond menu
sound_menu.song_changed(artist,album,title)

#when the player changes to/from the playing, it should inform the sound menu
sound_menu.signal_playing()
sound_menu.signal_paused()

#whent the song is changed from the application,
#use song_changed to inform the Ubuntu Sound Menu
sound_menu.song_changed(artist, album, song_title)

Configuring
SoundMenuControls does not come with any stock behaviors, so it
cannot be configured

Extending
SoundMenuControls can be used as a base class with single or multiple inheritance.

_sound_menu_next
_sound_menu_previous
_sound_menu_is_playing
_sound_menu_play
_sound_menu_pause

"""

class SoundMenuControls(dbus.service.Object):
    """
    SoundMenuControls - A class to make it easy to integrate with the Ubuntu Sound Menu.

    """

    def __init__(self, desktop_name):
        """
        Creates a SoundMenuControls object.

        Requires a dbus loop to be created before the gtk mainloop,
        typically by calling DBusGMainLoop(set_as_default=True).

        arguments:
        desktop_name: The name of the desktop file for the application,
        such as, "simple-player" to refer to the file: simple-player.desktop.

        """

        self.desktop_name = desktop_name
        bus_str = """org.mpris.MediaPlayer2.%s""" % desktop_name
        bus_name = dbus.service.BusName(name=bus_str, bus=dbus.SessionBus())
        dbus.service.Object.__init__(self, bus_name, "/org/mpris/MediaPlayer2")
        self.__playback_status = "Stopped"

        self.song_changed()

    def song_changed(self, artists = None, album = None, title = None, cover = None):
        """song_changed - sets the info for the current song.

        This method is not typically overriden. It should be called
        by implementations of this class when the player has changed
        songs.

        named arguments:
            artists - a list of strings representing the artists"
            album - a string for the name of the album
            title - a string for the title of the song

        """

        if artists is None:
            artists = [""]
        if album is None:
            album = ""
        if title is None:
            title = ""
        if cover is None:
            cover = ""

        self.__meta_data = dbus.Dictionary({"xesam:album":album,
                            "xesam:title":title,
                            "xesam:artist":artists,
                            "mpris:artUrl":cover,
                            }, "sv", variant_level=1)


    @dbus.service.method('org.mpris.MediaPlayer2')
    def Raise(self):
        """Raise

        A dbus signal handler for the Raise signal. Do no override this
        function directly. rather, overrise _sound_menu_raise. This
        function is typically only called by the Sound, not directly
        from code.

        """

        self._sound_menu_raise()

    def _sound_menu_raise(self):
        """ _sound_menu_raise -

        Override this function to bring the media player to the front
        when selected by the sound menu. For example, by calling
        app_window.get_window().show()

        """

        raise NotImplementedError("""@dbus.service.method('org.mpris.MediaPlayer2') Raise
                                      is not implemented by this player.""")


    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature='ss', out_signature='v')
    def Get(self, interface, prop):
        """Get

        A function necessary to implement dbus properties.

        This function is only called by the Sound Menu, and should not
        be overriden or called directly.

        """

        my_prop = self.__getattribute__(prop)
        return my_prop

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature='ssv')
    def Set(self, interface, prop, value):
        """Set

        A function necessary to implement dbus properties.

        This function is only called by the Sound Menu, and should not
        be overriden or called directly.

        """
        my_prop = self.__getattribute__(prop)
        my_prop = value

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface):
        """GetAll

        A function necessary to implement dbus properties.

        This function is only called by the Sound Menu, and should not
        be overriden or called directly.

        """

        return dict({"PlaylistCount":self.PlaylistCount(), "ActivePlaylist":self.ActivePlaylist, "DesktopEntry":self.DesktopEntry, "PlaybackStatus":self.PlaybackStatus, "MetaData":self.MetaData})

    @property
    def DesktopEntry(self):
        """DesktopEntry

        The name of the desktop file.

        This propert is only used by the Sound Menu, and should not
        be overriden or called directly.

        """

        return self.desktop_name

    @property
    def PlaybackStatus(self):
        """PlaybackStatus

        Current status "Playing", "Paused", or "Stopped"

        This property is only used by the Sound Menu, and should not
        be overriden or called directly.

        """

        return self.__playback_status

    @property
    def MetaData(self):
        """MetaData

        The info for the current song.

        This property is only used by the Sound Menu, and should not
        be overriden or called directly.

        """

        return self.__meta_data

    @dbus.service.method('org.mpris.MediaPlayer2.Player')
    def Next(self):
        """Next

        A dbus signal handler for the Next signal. Do no override this
        function directly. Rather, overide _sound_menu_next. This
        function is typically only called by the Sound, not directly
        from code.

        """

        self._sound_menu_next()

    def _sound_menu_next(self):
        """_sound_menu_next

        This function is called when the user has clicked
        the next button in the Sound Indicator. Implementations
        should overrirde this function in order to a function to
        advance to the next track. Implementations should call
        song_changed() and sound_menu.signal_playing() in order to
        keep the song information in the sound menu in sync.

        The default implementation of this function has no effect.

        """
        pass

    @dbus.service.method('org.mpris.MediaPlayer2.Player')
    def Previous(self):
        """Previous

        A dbus signal handler for the Previous signal. Do no override this
        function directly. Rather, overide _sound_menu_previous. This
        function is typically only called by the Sound Menu, not directly
        from code.

        """


        self._sound_menu_previous()

    def _sound_menu_previous(self):
        """_sound_menu_previous

        This function is called when the user has clicked
        the previous button in the Sound Indicator. Implementations
        should overrirde this function in order to a function to
        advance to the next track. Implementations should call
        song_changed() and  sound_menu.signal_playing() in order to
        keep the song information in sync.

        The default implementation of this function has no effect.


        """
        pass

    @dbus.service.method('org.mpris.MediaPlayer2.Player')
    def PlayPause(self):
        """Next

        A dbus signal handler for the Next signal. Do no override this
        function directly. Rather, overide _sound_menu_next. This
        function is typically only called by the Sound, not directly
        from code.

        """

        if not self._sound_menu_is_playing():
            self._sound_menu_play()
            self.signal_playing()
        else:
            self._sound_menu_pause()
            self.signal_paused()

    def signal_playing(self):
        """signal_playing - Tell the Sound Menu that the player has
        started playing. Implementations many need to call this function in order
        to keep the Sound Menu in synch.

        arguments:
            none

        """
        self.__playback_status = "Playing"
        d = dbus.Dictionary({"PlaybackStatus":self.__playback_status, "Metadata":self.__meta_data},
                                    "sv",variant_level=1)
        self.PropertiesChanged("org.mpris.MediaPlayer2.Player",d,[])

    def signal_paused(self):
        """signal_paused - Tell the Sound Menu that the player has
        been paused. Implementations many need to call this function in order
        to keep the Sound Menu in synch.

        arguments:
            none

        """

        self.__playback_status = "Paused"
        d = dbus.Dictionary({"PlaybackStatus":self.__playback_status},
                                    "sv",variant_level=1)
        self.PropertiesChanged("org.mpris.MediaPlayer2.Player",d,[])


    def _sound_menu_is_playing(self):
        """_sound_menu_is_playing

        Check if the the player is playing,.
        Implementations should overrirde this function
        so that the Sound Menu can check whether to display
        Play or Pause functionality.

        The default implementation of this function always
        returns False.

        arguments:
            none

        returns:
            returns True if the player is playing, otherwise
            returns False if the player is stopped or paused.
        """

        return False

    def _sound_menu_pause(self):
        """_sound_menu_pause

        Reponds to the Sound Menu when the user has click the
        Pause button.

        Implementations should overrirde this function
        to pause playback when called.

        The default implementation of this function does nothing

        arguments:
            none

        returns:
            None

       """

        pass

    def _sound_menu_play(self):
        """_sound_menu_play

        Reponds to the Sound Menu when the user has click the
        Play button.

        Implementations should overrirde this function
        to play playback when called.

        The default implementation of this function does nothing

        arguments:
            none

        returns:
            None

       """

        pass

    @dbus.service.signal(dbus.PROPERTIES_IFACE, signature='sa{sv}as')
    def PropertiesChanged(self, interface_name, changed_properties,
                          invalidated_properties):
        """PropertiesChanged

        A function necessary to implement dbus properties.

        Typically, this function is not overriden or called directly.

        """

        pass

    @dbus.service.method('org.mpris.MediaPlayer2.Playlists',
                         in_signature='s', out_signature='')
    def ActivatePlaylist(self, playlist_id):
        """ ActivatePlaylist

        A dbus signal handler to activate a playlist
        """

        self._activate_playlist(playlist_id)

    def _activate_playlist(self, playlist):
        """ _activate_playlist -

        Override this function to begin playing the selected playlist
        """

        raise NotImplementedError("""@dbus.service.method('org.mpris.MediaPlayer2.Playlists')
                                     ActivatePlaylist is not implemented by this player.""")

    @dbus.service.method('org.mpris.MediaPlayer2.Playlists',
                         in_signature='uusb', out_signature='a(sss)')
    def GetPlaylists(self, index, maxCount, order, reverseOrder):
        """GetPlaylists

        A dbus signal handler to supply playlist information
        """

        playlists = self._get_playlists(index, maxCount, order, reverseOrder)
        return playlists

    def _get_playlists(self, index, maxCount, order, reverseOrder):
        """ _get_playlists-

        Override this function to provide a list of available playlists
        """

        raise NotImplementedError("""@dbus.service.method('org.mpris.MediaPlayer2.Playlists')
                                     GetPlaylists is not implemented by this player.""")

    @property
    def PlaylistCount(self):
        """PlaylistCount

        The number of playlists available

        This property is only used by the Sound Menu, and should not
        be overriden or called directly.

        """

        return self.playlist_count

    @property
    def Orderings(self):
        """Orderings

        The ordering for the list of playlists

        This property is only used by the Sound Menu, and should not
        be overriden or called directly.

        """

        self.order = ["User"]
        return self.order

    @property
    def ActivePlaylist(self):
        """ActivePlaylist

        The currently active playlist

        This property is only used by the Sound Menu, and should not
        be overriden or called directly.

        """

        return self._active_playlist()


    def _active_playlist():
        """
        Override to provide list active playlist
        """
        return (False, ("/", "", ""))

    def _signal_active_playlist(self):
        d = dbus.Dictionary({"ActivePlaylist":self._active_playlist()},
                                    "sv",variant_level=1)
        self.PropertiesChanged("org.mpris.MediaPlayer2.Playlists",d,[])

    def _signal_playlist_count(self):
        d = dbus.Dictionary({"PlaylistCount":len(self._get_playlists())},
                                    "sv",variant_level=1)
        self.PropertiesChanged("org.mpris.MediaPlayer2.Playlists",d,[])

x = XMMS2USM()

