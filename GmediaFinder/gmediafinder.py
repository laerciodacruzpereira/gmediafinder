#!/usr/bin/env python
#-*- coding: UTF-8 -*-

import sys
import os
import thread
import threading
import time
import gobject
import pygtk
pygtk.require('2.0')
import gtk
import gtk.glade
import urllib
import urllib2
import httplib
import socket
import pygst
pygst.require("0.10")
import gst
import re
import html5lib
import tempfile
import time
from html5lib import sanitizer, treebuilders, treewalkers, serializer, treewalkers
import traceback
import gdata.service
from configobj import ConfigObj

from BeautifulSoup import BeautifulSoup, NavigableString, BeautifulStoneSoup
import HTMLParser

## custom lib
try:
    from GmediaFinder import constants
except:
    import constants

# timeout in seconds
timeout = 10
socket.setdefaulttimeout(timeout)

class GsongFinder(object):
    def __init__(self):
        ## default search options
        self.is_playing = False
        self.duration = None
        self.time_label = gtk.Label("00:00 / 00:00")
        self.search_thread_id = None
        self.media_name = ""
        self.media_link = ""
        self.nbresults = 100
        self.user_search = ""
        self.play_options = None
        self.fullscreen = False
        self.play_options = None
        self.mini_player = True
        self.timer = 0
        self.settings_folder = None
        self.conf_file = None
        self.youtube_max_res = "320x240"
        if sys.platform == "win32":
            from win32com.shell import shell, shellcon
            df = shell.SHGetDesktopFolder()
            pidl = df.ParseDisplayName(0, None,"::{450d8fba-ad25-11d0-98a8-0800361b1103}")[1]
            mydocs = shell.SHGetPathFromIDList(pidl)
            self.down_dir = os.path.join(mydocs,"gmediafinder-downloads")
            self.settings_folder = os.path.join(shell.SHGetFolderPath(0, shellcon.CSIDL_APPDATA, 0, 0),"gmediafinder")
        else:
            self.down_dir = os.path.join(os.getenv('HOME'),"gmediafinder-downloads")
            self.settings_folder = os.path.join(os.getenv('HOME'),".config/gmediafinder")

        ## conf file
        self.conf_file = os.path.join(self.settings_folder, 'gmediafinder_config')
        if not os.path.exists(self.settings_folder):
            os.mkdir(self.settings_folder)
            fd = os.open(self.conf_file, os.O_RDWR|os.O_CREAT)
            os.write(fd,"youtube_max_res=%s" % self.youtube_max_res)
            os.close(fd)
        self.config = ConfigObj(self.conf_file,write_empty_values=True)
        ## get default max_res for youtube videos
        self.youtube_max_res = self.config["youtube_max_res"]
        
        self.engine_list = {'youtube.com':'','google.com':'','tagoo.ru':'','dilandau.com':'','mp3realm.org':'','iwantmuzik.com':''}
        self.engine = None
        self.search_option = "song_radio"
        self.banned_sites = ['worxpress','null3d','audiozen']
        self.search_requests = {'song_radio':'(mp3|wav|wmv|aac|ogg) "index of "',
                                'video_radio' : '(avi|ogv|mpg|mpeg|wmv|mp4) "index of "',
                                'img_radio':'(png|jpeg|jpg|svg|gif) "index of "',
                                }
        ## small config dir for downloads...
        if not os.path.exists(self.down_dir):
            os.mkdir(self.down_dir)
        ## Get Icons shown on buttons
        settings = gtk.settings_get_default()
        gtk.Settings.set_long_property(settings, "gtk-button-images", 1, "main")
        
        ## gui
        self.gladeGui = gtk.glade.XML(constants.glade_file, None ,constants.app_name)
        self.window = self.gladeGui.get_widget("main_window")
        self.window.set_title("Gmediafinder")
        self.window.set_resizable(1)
        self.window.set_size_request(780, 560)
        self.window.set_position(gtk.WIN_POS_CENTER_ALWAYS)
        if ('/usr' in constants.exec_path):
            self.img_path = '/usr/share/gmediafinder'
        else:
            self.img_path = os.path.join(constants.img_path)
        self.window.set_icon_from_file(os.path.join(self.img_path,'gmediafinder.png'))
        self.window.connect('key-press-event', self.onKeyPress)
        ## informations
        self.top_infobox = self.gladeGui.get_widget("top_info")
        self.informations_label = self.gladeGui.get_widget("info_label")
        # options menu
        self.options_bar = self.gladeGui.get_widget("options_bar")
        self.about_btn= self.gladeGui.get_widget("about_menu")
        self.settings_btn= self.gladeGui.get_widget("settings_menu")
        
        ## youtube video quality choices
        self.res320 = self.gladeGui.get_widget("res1")
        self.res640 = self.gladeGui.get_widget("res2")
        self.res854 = self.gladeGui.get_widget("res3")
        self.res1280 = self.gladeGui.get_widget("res4")
        self.res1920 = self.gladeGui.get_widget("res5")
        
        ## google search options
        self.search_box = self.gladeGui.get_widget("search_box")
        self.results_box = self.gladeGui.get_widget("results_box")
        self.options_box = self.gladeGui.get_widget("options_box")
        self.option_songs = self.gladeGui.get_widget("song_radio")
        self.option_videos = self.gladeGui.get_widget("video_radio")
        self.option_images = self.gladeGui.get_widget("img_radio")
        ## engine selector (engines only with direct links)
        self.engine_selector = self.gladeGui.get_widget("engine_selector")
        for engine in self.engine_list:
            self.engine_selector.append_text(engine)
        
        # youtube search options
        self.youtube_options = self.gladeGui.get_widget("youtube_options")
        self.youtube_options.relevance_opt = self.gladeGui.get_widget("relevance_opt")
        self.youtube_options.recent_opt = self.gladeGui.get_widget("most_recent_opt")
        self.youtube_options.relevance_opt.set_active(True)
        self.youtube_options.viewed_opt = self.gladeGui.get_widget("most_viewed_opt")
        self.youtube_options.rating_opt = self.gladeGui.get_widget("rating_opt")
        ## video quality combobox
        youtube_quality_box = self.gladeGui.get_widget("youtube_quality_box")
        self.youtube_quality_model = gtk.ListStore(str)
        self.youtube_video_rate = gtk.ComboBox(self.youtube_quality_model)
        cell = gtk.CellRendererText()
        self.youtube_video_rate.pack_start(cell, True)
        self.youtube_video_rate.add_attribute(cell, 'text', 0)
        youtube_quality_box.add(self.youtube_video_rate)
        new_iter = self.youtube_quality_model.append()
        self.youtube_quality_model.set(new_iter,
                                0, "Quality",
                                )
        self.youtube_video_rate.connect('changed', self.on_youtube_video_rate_changed)
        
        ## control section
        self.play_btn = self.gladeGui.get_widget("play_btn")
        self.pause_btn = self.gladeGui.get_widget("pause_btn")
        self.volume_btn = self.gladeGui.get_widget("volume_btn")
        self.play_btn.connect('clicked', self.start_stop)
        self.down_btn = self.gladeGui.get_widget("down_btn")

        self.continue_checkbox = self.gladeGui.get_widget("continue_checkbox")
        self.continue_checkbox.set_active(1)
        self.play_options = "continue"
        self.loop_checkbox = self.gladeGui.get_widget("loop_checkbox")
        ## search bar
        self.search_entry = self.gladeGui.get_widget("search_entry")
        self.search_btn = self.gladeGui.get_widget("search_btn")
        self.changepage_btn = self.gladeGui.get_widget("changepage_btn")

        ## statbar
        self.statbar = self.gladeGui.get_widget("statusbar")

        # progressbar
        self.progressbar = self.gladeGui.get_widget("progressbar")

        # video drawing
        self.video_box = self.gladeGui.get_widget("video_box")
        self.movie_window = self.gladeGui.get_widget("drawingarea")
        self.movie_window.set_flags(gtk.CAN_FOCUS)
        self.movie_window.unset_flags(gtk.DOUBLE_BUFFERED)
        self.movie_window.connect('realize', self.on_drawingarea_realized)
        self.window.connect('motion-notify-event', self.on_motion_notify)
        self.movie_window.connect('configure-event', self.on_configure_event)
        self.movie_window.connect('expose-event', self.on_expose_event)
        self.movie_window.connect('button-press-event', self.on_drawingarea_clicked)
        self.movie_window.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.pic_box = self.gladeGui.get_widget("picture_box")
        
        # seekbar and signals
        self.control_box = self.gladeGui.get_widget("control_box")
        self.seekbox = self.gladeGui.get_widget("seekbox")
        self.adjustment = gtk.Adjustment(0.0, 0.00, 100.0, 0.1, 1.0, 1.0)
        self.seeker = gtk.HScale(self.adjustment)
        self.seeker.set_draw_value(False)
        self.seeker.set_update_policy(gtk.UPDATE_DISCONTINUOUS)
        self.seekbox.add(self.seeker)
        self.seeker.connect("button-release-event", self.seeker_button_release_event)
        
        #timer
        self.timerbox = self.gladeGui.get_widget("timer_box")
        self.timerbox.add(self.time_label)
        
        ## youtube client
        self.youtube = YouTubeClient()
        
        ## visualisations
        self.vis_selector = self.gladeGui.get_widget("vis_chooser")
        
        
        ## SIGNALS
        dic = {"on_main_window_destroy_event" : self.exit,
        "on_song_radio_toggled" : self.option_changed,
        "on_video_radio_toggled" :  self.option_changed,
        "on_img_radio_toggled" :  self.option_changed,
        "on_search_btn_clicked" : self.prepare_search,
        "on_engine_selector_changed" : self.set_engine,
        "on_quit_menu_activate" : self.exit,
        "on_pause_btn_clicked" : self.pause_resume,
        "on_down_btn_clicked" : self.download_file,
        "on_changepage_btn_clicked" : self.change_page,
        "on_search_entry_activate" : self.prepare_search,
        "on_continue_checkbox_toggled" : self.set_play_options,
        "on_loop_checkbox_toggled" : self.set_play_options,
        "on_vol_btn_value_changed" : self.on_volume_changed,
        "on_vis_chooser_changed" : self.change_visualisation,
        "on_about_menu_activate" : self.on_about_btn_pressed,
        "on_settings_menu_activate" : self.on_settings_btn_pressed,
        "on_res1_toggled" : self.set_max_youtube_res,
        "on_res2_toggled" : self.set_max_youtube_res,
        "on_res3_toggled" : self.set_max_youtube_res,
        "on_res4_toggled" : self.set_max_youtube_res,
        "on_res5_toggled" : self.set_max_youtube_res,
         }
        self.gladeGui.signal_autoconnect(dic)
        self.window.connect('destroy', self.exit)

        ## finally setup the list
        (COL_PIXBUF, COL_STRING) = range(2)
        self.model = gtk.ListStore(gtk.gdk.Pixbuf,str,object,object)
        self.treeview = gtk.TreeView()
        self.treeview.set_model(self.model)
        
        column = gtk.TreeViewColumn()
        column.set_title(' Results : ')
        self.treeview.append_column(column)

        rendererp = gtk.CellRendererPixbuf()
        column.pack_start(rendererp, expand=False)
        column.add_attribute(rendererp, 'pixbuf', COL_PIXBUF)

        renderer = gtk.CellRendererText()
        renderer.set_fixed_size(200,60)
        column.pack_start(renderer, expand=True)
        column.add_attribute(renderer, 'text', COL_STRING)
        
        pathColumn = gtk.TreeViewColumn("Link", renderer, text=0)
        self.treeview.append_column(pathColumn)
        
        qualityColumn = gtk.TreeViewColumn("Quality", renderer, text=0)
        self.treeview.append_column(qualityColumn)
        
        ## setup the scrollview
        self.results_scroll = self.gladeGui.get_widget("results_scrollbox")
        self.columns = self.treeview.get_columns()
        self.columns[0].set_sort_column_id(1)
        self.columns[1].set_visible(0)
        self.columns[2].set_visible(0)
        self.results_scroll.add(self.treeview)
        ## connect treeview signals
        self.treeview.connect('cursor-changed',self.get_model)

        ## create the players
        self.player = gst.element_factory_make("playbin", "player")
        audiosink = gst.element_factory_make("autoaudiosink")
        self.vis = self.change_visualisation()
        if sys.platform == "win32":
            self.sink = gst.element_factory_make('d3dvideosink')
        else:
            self.sink = gst.element_factory_make('xvimagesink')
            if self.engine == "youtube.com":
                self.sink.set_property('force-aspect-ratio', True)
        self.player.set_property("audio-sink", audiosink)
        self.player.set_property('video-sink', self.sink)
        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect("message", self.on_message)
        bus.connect("sync-message::element", self.on_sync_message)


        ## time
        self.timeFormat = gst.Format(gst.FORMAT_TIME)

        ## start gui
        self.window.show_all()
        self.progressbar.hide()
        self.changepage_btn.hide()
        self.options_box.hide()
        self.youtube_options.hide()
        self.youtube_video_rate.hide()
        
        self.engine_selector.set_active(0)
        self.youtube_video_rate.set_active(0)
        ## start main loop
        gobject.threads_init()
        #gtk.gdk.threads_init()
        self.mainloop = gobject.MainLoop(is_running=True)
        self.mainloop.run()
        
    def change_visualisation(self, widget=None):
        vis = self.vis_selector.get_active_text()
        if vis == "":
            self.vis_selector.set_active(0)
            self.vis = "libvisual_jess"
        elif vis != "goom":
            self.vis = "libvisual_"+vis
        else:
            self.vis = vis
        return self.vis

    def set_engine(self,widget=None):
        self.options_box.hide()
        self.youtube_options.hide()
        self.youtube_video_rate.hide()
        self.engine = self.engine_selector.get_active_text()
        self.changepage_btn.hide()
        iter = self.engine_selector.get_active_iter()
        if self.engine == "Select an engine":
            self.engine = None
            return
        print "%s engine selected" % self.engine
        if self.engine == "google.com":
            self.options_box.show()
            self.option_songs.set_active(1)
        elif self.engine == "youtube.com":
            self.youtube_options.show()
            self.youtube_video_rate.show()
            self.youtube_options.relevance_opt.set_active(1)
            

    def reset_pages(self):
        self.changepage_btn.hide()
        if self.engine == "mp3realm.org":
            self.req_start = 1
        elif self.engine == "dilandau.com":
            self.req_start = 1
        elif self.engine == "tagoo.ru":
            self.req_start = 1
        elif self.engine == "skreemr.com":
            self.req_start = 10
            self.page = 1
        elif self.engine == "youtube.com":
            self.req_start = 0
        elif self.engine == "iwantmuzik.com":
            self.req_start = 1

    def get_model(self,widget):
        selected = self.treeview.get_selection()
        self.iter = selected.get_selected()[1]
        self.path = self.model.get_path(self.iter)
        ## else extract needed metacity's infos
        self.media_name = self.model.get_value(self.iter, 1)
        ## return only theme name and description then extract infos from hash
        self.media_link = self.model.get_value(self.iter, 2)
        # print in the gui
        self.statbar.push(1,"Playing : %s" % self.media_name)
        self.stop_play()
        ## check youtube quality
        if self.engine == "youtube.com":
            self.quality_list = self.model.get_value(self.iter, 3)
            self.youtube_quality_model.clear()
            if not self.quality_list:
                return
            for rate in self.quality_list:
                new_iter = self.youtube_quality_model.append()
                self.youtube_quality_model.set(new_iter,
                                0, rate,
                                )
            self.set_default_youtube_video_rate()
        else:
			self.start_play(self.media_link)
        
    def option_changed(self,widget):
        self.search_option = widget.name


    def prepare_search(self,widget=None):
        self.user_search = self.search_entry.get_text()
        if not self.user_search:
            self.informations_label.set_text("Please enter an artist/album or song name...")
            return
        if not self.engine:
            self.informations_label.set_text("Please select an engine...")
            return
        self.main_engine = self.engine_selector.get_active_text()
        self.reset_pages()

        return self.get_page_links()

    def change_page(self,widget=None):
        user_search = self.search_entry.get_text()
        engine = self.engine_selector.get_active_text()
        if not user_search or user_search != self.user_search \
        or not engine or engine != self.main_engine:
            self.reset_pages()
            return self.prepare_search()
        else:
            return self.get_page_links()


    ## main search to receive original search when requesting next pages...
    def get_page_links(self,widget=None):
        self.url = self.search()
        self.data = self.get_url_data(self.url)
        self.start_search()

    def search(self):
        self.model.clear()
        self.informations_label.set_text("Searching for %s with %s " % (self.user_search,self.engine))
        ## encode the name
        user_search = urllib2.quote(self.user_search)
        ## prepare the request
        if self.engine == None:
            self.informations_label.set_text("Please select a search engine...")
            return
        urlopt = ""
        baseurl = ""
        if self.engine == "google.com":
            baseurl = "http://www.google.fr/search?num=100&ie=UTF-8&q="
            urlopt = urllib.quote(self.search_requests[self.search_option]) +'%20'+user_search
            url = baseurl + urlopt
        elif self.engine == "mp3realm.org":
            url = "http://mp3realm.org/search?q=%s&bitrate=&dur=0&pp=50&page=%s" % (user_search,self.req_start)
        elif self.engine == "dilandau.com":
            url = "http://fr.dilandau.com/telecharger_musique/%s-%d.html" % (user_search,self.req_start)
        elif self.engine == "tagoo.ru":
            url = "http://tagoo.ru/en/search.php?for=audio&search=%s&page=%d&sort=date" % (user_search,self.req_start)
        elif self.engine == "youtube.com":
            url = "http://www.youtube.com/results?search_query=%s&page=%s" % (user_search,self.req_start)
        elif self.engine == "iwantmuzik.com":
            url = "http://iwantmuzik.com/search/mp3/%s/%s.html" % (self.req_start,user_search)
        ## 1 for first resquest to not test content type
        return url

    def get_url_data(self,url):
        user_agent = 'Mozilla/5.0 (X11; U; Linux i686; en-US) AppleWebKit/534.15 (KHTML, like Gecko) Ubuntu/10.10 Chromium/10.0.608.0 Chrome/10.0.608.0 Safari/534.15'
        headers =  { 'User-Agent' : user_agent , 'Accept-Language' : 'fr-FR,fr;q=0.8,en-US;q=0.6,en;q=0.4' }
        ## start the request
        try:
            req = urllib2.Request(url,None,headers)
        except:
            return
        try:
            code = urllib2.urlopen(req)
        except:
            return

        # si besoin
        #results = self.clean_html(code.read())

        results = code.read()
        return results

    def analyse_links(self):
        data = self.data
        url = self.url
        search_thread_id = self.search_thread_id
        gtk.gdk.threads_enter()
        self.informations_label.set_text("Searching for %s with %s" % (self.user_search,self.engine))
        gtk.gdk.threads_leave()
        HTMLParser.attrfind = re.compile(r'\s*([a-zA-Z_][-.:a-zA-Z_0-9]*)(\s*=\s*'r'(\'[^\']*\'|"[^"]*"|[^\s>^\[\]{}\|\'\"]*))?')

        if data:
            soup = BeautifulStoneSoup(data)
            if self.engine == "google.com":
                try:
                    alist = soup.findAll('a', href=True)
                    #gtk.gdk.threads_enter()
                    for a in alist:
                        url = a.attrMap['href']
                        if not url: continue
                        if re.search('href="(\S.*>Index of)', a.__str__()):
                            self.informations_label.set_text("Media files detected on : %s, scanning... " % (urllib2.unquote(url)))
                            verified_links = self.check_google_links(url)
                            if verified_links:
                                slist = verified_links.findAll('a', href=True)
                                #gtk.gdk.threads_leave()
                                ## if ok start the loop
                                #gtk.gdk.threads_enter()
                                for s in slist:
                                    print "scanning webpage : %s" % s.string
                                    try:
                                        req = re.search('(.*%s.*)(.mp3|.mp4|.ogg|.aac|.wav|.wma|.wmv|.avi|.mpg|.mpeg|.mkv|.ogv)' % self.user_search.lower(), urllib2.unquote(s.__str__().lower())).group()
                                    except:
                                        continue
                                    link = url + s.attrMap['href']
                                    name = urllib2.unquote(os.path.basename(link))
                                    self.add_sound(name, link)
                            else:
                                continue
                except:
                    #gtk.gdk.threads_leave()
                    pass
                self.search_thread_id = None
                self.informations_label.set_text("Scan terminated for your request : %s" % self.user_search)

            elif self.engine == "mp3realm.org":
                soup = BeautifulStoneSoup(self.clean_html(data).decode('UTF8'))
                ## reset the treeview
                nlist = []
                link_list = []
                files_count = None
                try:
                    #search results div
                    files_count = soup.findAll('div',attrs={'id':'searchstat'})[0].findAll('strong')[1].string
                except:
                    self.informations_label.set_text("no results found for %s..." % (self.user_search))
                    self.search_thread_id = None
                    return

                self.informations_label.set_text("%s files found for %s" % (files_count, self.user_search))
                if re.search(r'(\S*Aucuns resultats)', soup.__str__()):
                    self.changepage_btn.hide()
                    self.req_start = 1
                    self.informations_label.set_text("no more files found for %s..." % (self.user_search))
                    self.search_thread_id = None
                    return
                else:
                    self.informations_label.set_text("Results page %s for %s...(%s results)" % (self.req_start, self.user_search,files_count))
                    self.req_start += 1

                self.changepage_btn.show()
                flist = re.findall('(http://.*\S\.mp3|\.mp4|\.ogg|\.aac|\.wav|\.wma)', data.lower())
                for link in flist:
                    if re.match('http://\'\+this', link) :
                        continue
                    try:
                        link = urllib2.unquote(link)
                        name = urllib2.unquote(os.path.basename(link.decode('UTF8')))
                        nlist.append(name)
                        link_list.append(link)
                    except:
                        continue
                ## add to the treeview if ok
                i = 0
                for name in nlist:
                    if name and link_list[i]:
                        self.add_sound(name, link_list[i])
                        i += 1

            elif self.engine == "dilandau.com":
                soup = BeautifulStoneSoup(self.clean_html(data).encode('utf-8'),selfClosingTags=['/>'])
                nlist = []
                link_list = []
                next_page = 1
                try:
                    pagination_table = soup.findAll('div',attrs={'class':'pages'})[0]
                except:
                    self.changepage_btn.hide()
                    self.informations_label.set_text("no files found for %s..." % (self.user_search))
                    self.search_thread_id = None
                    return
                if pagination_table:
                    next_check = pagination_table.findAll('a',attrs={'class':'pages'})
                    for a in next_check:
                        l = str(a.string)
                        if l == "Suivante >>":
                            next_page = 1
                    if next_page:
                        self.informations_label.set_text("Results page %s for %s...(Next page available)" % (self.req_start, self.user_search))
                        self.req_start += 1
                        self.changepage_btn.show()
                    else:
                        self.changepage_btn.hide()
                        self.req_start = 1
                        self.informations_label.set_text("no more files found for %s..." % (self.user_search))
                        self.search_thread_id = None
                        return

                flist = [ each.get('href') for each in soup.findAll('a',attrs={'class':'button download_button'}) ]
                for link in flist:
                    try:
                        link = urllib2.unquote(link)
                        name = urllib2.unquote(os.path.basename(link.decode('utf-8')))
                        nlist.append(name)
                        link_list.append(link)
                    except:
                        continue
                ## add to the treeview if ok
                i = 0
                for name in nlist:
                    if name and link_list[i]:
                        self.add_sound(name, link_list[i])
                        i += 1
                        
            elif self.engine == "iwantmuzik.com":
                soup = BeautifulStoneSoup(self.clean_html(data).encode('utf-8'),selfClosingTags=['/>'])
                nlist = []
                link_list = []
                next_page = 1
                pagination_table = soup.findAll('table',attrs={'class':'pagination'})[0]
                if pagination_table:
                    next_check = pagination_table.findAll('a')
                    for a in next_check:
                        l = str(a.string)
                        if l == "More results":
                            next_page = 1
                    if next_page:
                        self.informations_label.set_text("Results page %s for %s...(Next page available)" % (self.req_start, self.user_search))
                        self.req_start += 1
                        self.changepage_btn.show()
                    else:
                        self.changepage_btn.hide()
                        self.req_start = 1
                        self.informations_label.set_text("no more files found for %s..." % (self.user_search))
                        self.search_thread_id = None
                        return

                flist = soup.findAll('div',attrs={'class':'download_link'})
                if len(flist) == 0:
                    self.changepage_btn.hide()
                    self.informations_label.set_text("no files found for %s..." % (self.user_search))
                    self.search_thread_id = None
                    return
                for link in flist:
                    try:
                        url = re.search('a href="(http\S+.mp3)',str(link)).group(1)
                        link = urllib2.unquote(url)
                        name = urllib2.unquote(os.path.basename(link.decode('utf-8')))
                        nlist.append(name)
                        link_list.append(link)
                    except:
                        continue
                ## add to the treeview if ok
                i = 0
                for name in nlist:
                    if name and link_list[i]:
                        self.add_sound(name, link_list[i])
                        i += 1

            elif self.engine == "tagoo.ru":
                soup = BeautifulStoneSoup(self.clean_html(data).decode('utf-8'),selfClosingTags=['/>'])
                nlist = []
                link_list = []
                next_page = 1
                results_div = soup.find('div',attrs={'class':'resultinfo'})
                try:
                    results_count = re.search('Found about (\d+)', str(results_div)).group(1)
                except:
                    self.changepage_btn.hide()
                    self.informations_label.set_text("No results found for %s..." % (self.user_search))
                    self.search_thread_id = None
                    return
                if results_count == 0 :
                    self.informations_label.set_text("no results for your search : %s " % (self.user_search))
                    return
                else:
                    self.informations_label.set_text("%s results found for your search : %s " % (results_count, self.user_search))

                pagination_table = soup.findAll('div',attrs={'class':'pages'})[0]
                if pagination_table:
                    next_check = pagination_table.findAll('a')
                    for a in next_check:
                        l = str(a.string)
                        if l == "Next":
                            next_page = 1
                    if next_page:
                        self.informations_label.set_text("Results page %s for %s...(%s results)" % (self.req_start, self.user_search,results_count))
                        self.req_start += 1
                        self.changepage_btn.show()
                    else:
                        self.changepage_btn.hide()
                        self.req_start = 1
                        self.informations_label.set_text("no more files found for %s..." % (self.user_search))
                        self.search_thread_id = None
                        return

                flist = [ each.get('href') for each in soup.findAll('a',attrs={'class':'link'}) ]
                for link in flist:
                    try:
                        link = urllib2.unquote(link)
                        name = urllib2.unquote(os.path.basename(link.decode('utf-8')))
                        nlist.append(name)
                        link_list.append(link)
                    except:
                        continue
                ## add to the treeview if ok
                i = 0
                for name in nlist:
                    if name and link_list[i]:
                        self.add_sound(name, link_list[i])
                        i += 1

            elif self.engine == "youtube.com":
                nlist = []
                link_list = []
                next_page = 0
                self.changepage_btn.show()
                ## get options
                params = None
                if self.youtube_options.relevance_opt.get_active():
                    params="&orderby=relevance"
                elif self.youtube_options.recent_opt.get_active():
                    params="&orderby=published"
                elif self.youtube_options.viewed_opt.get_active():
                    params="&orderby=viewCount"
                elif self.youtube_options.rating_opt.get_active():
                    params="&orderby=rating"
                
                if self.req_start == 0:
                    self.req_start = 1
                elif self.req_start == 1:
                    self.req_start = 26
                else:
                    self.req_start+=25
                        
                vquery = self.youtube.search(self.user_search,self.req_start,params)
                if len(vquery) == 0:
                    self.changepage_btn.hide()
                    self.informations_label.set_text("no more files found for %s..." % (self.user_search))
                    self.search_thread_id = None
                    return
                
                #flist = [ each.get('href') for each in soup.findAll('a',attrs={'class':'ux-thumb-wrap contains-addto'}) ]
                for video in vquery:
                    self.make_youtube_entry(video)
                self.search_thread_id = None
        else:
            return
        self.search_thread_id = None


    def sanitizer_factory(self,*args, **kwargs):
        san = sanitizer.HTMLSanitizer(*args, **kwargs)
        # This isn't available yet
        # san.strip_tokens = True
        return san

    def clean_html(self,buf):
        """Cleans HTML of dangerous tags and content."""
        buf = buf.strip()
        if not buf:
            return buf

        p = html5lib.HTMLParser(tree=treebuilders.getTreeBuilder("dom"),
                tokenizer=self.sanitizer_factory)
        dom_tree = p.parseFragment(buf)

        walker = treewalkers.getTreeWalker("dom")
        stream = walker(dom_tree)

        s = serializer.htmlserializer.HTMLSerializer(
                omit_optional_tags=False,
                quote_attr_values=False)
        return s.render(stream).decode('UTF-8')


    def check_google_links(self,url):
        ## test the link for audio file on first scan
        subreq = self.get_url_data(url)
        try:
            subsoup = BeautifulSoup(''.join(subreq))
        except:
            return
        ## first check if content is readeable
        try:
            name = re.search('href="(\S.*)(.mp3|.mp4|.ogg|.aac|.wav|.wma|.wmv|.avi|.mpeg|.mpg|.ogv)"', urllib2.unquote(subsoup.__str__().lower())).group(1,2)
        except:
            return
        original_name = req = re.search('href="(\S.*)(.mp3|.mp4|.ogg|.aac|.wav|.wma|.wmv|.avi|.mpeg|.ogv|.mpg)"', urllib2.unquote(subsoup.__str__())).group(1,2)
        file = ''.join(original_name)
        print "file to test content-type: %s" % file
        try:
            coded_name = urllib2.quote(file)
            coded_link = os.path.join(url, coded_name)
            req = urllib.urlopen(coded_link)
            req.close()
        except:
            return
        ## test headers
        type = req.headers.get("content-type")

        exp_reg = re.compile("(audio|video)")
        if re.search(exp_reg, type):
            print "%s type detected ok, sounds from this website added to the playlist" % type
            return subsoup
        else:
            print "wrong media type %s, link to another webpage...website rejected" % type
            return

    def add_sound(self, name, media_link, img=None, quality_list=None):
        if not name or not media_link:
            return
        self.iter = self.model.append()
        if self.engine == "youtube.com":
            img_data = self.download_photo(img)
            img = gtk.gdk.pixbuf_new_from_file(img_data)
        else:
            img = gtk.gdk.pixbuf_new_from_file_at_scale(os.path.join(self.img_path,'sound.png'), 64,64, 1)
        self.model.set(self.iter,
                        0, img,
                        1, name,
                        2, media_link,
                        3, quality_list,
                        )
                       
    def download_photo(self, img_url):
        filename = os.path.basename(img_url)
        if sys.platform == "win32":
            file_path = os.path.join(tempfile.gettempdir(), filename)
        else:
            file_path = "%s%s" % ('/tmp/', filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        downloaded_image = file(file_path, "wb")

        image_on_web = urllib.urlopen(img_url)
        while True:
            buf = image_on_web.read(65536)
            if len(buf) == 0:
                break
            downloaded_image.write(buf)
        downloaded_image.close()
        image_on_web.close()

        return file_path


    def search_pic(self):
        name = os.path.splitext(self.media_name)[0].lower()
        if not name:
            return
        user_search = urllib2.quote(name)
        data = self.get_url_data('http://www.soundunwound.com/sp/release/find?searchPhrase='+user_search)
        if data:
            soup = BeautifulSoup(''.join(data))
        else:
            return
        files_count = soup.findAll('td',attrs={'class':'image'})
        if len(files_count) > 0:
            alist = soup.findAll('a', href=True)
        for link in alist:
            value = link.attrMap['href']
            if re.search('(\S.*%s)' % name, value):
                print link
                
    def make_youtube_entry(self,video):
        url = video.link[1].href
        vid_id = os.path.basename(os.path.dirname(url))    
        try:
            vid_obj,links_arr,quality_arr = _GetYoutubeVideoInfo(vid_id)
        except:
            return
        vid_pic = vid_obj["thumbnail_url"]
        vid_title = vid_obj["title"]
        name = vid_title
        if not name or not links_arr:
            return
        else:
            return self.add_sound(name, links_arr, vid_pic, quality_arr)
            
    def set_default_youtube_video_rate(self,widget=None):
		active = self.youtube_video_rate.get_active()
		qn = 0
		## if there s only one quality available, read it...
		if active == -1:
			if len(self.quality_list) == 1:
				self.youtube_video_rate.set_active(0)
			for frate in self.quality_list:
				rate = frate.split('|')[0]
				h = int(rate.split('x')[0])
				dh = int(self.youtube_max_res.split('x')[0])
				if h > dh:
					qn+=1
					continue
				else:
					self.youtube_video_rate.set_active(qn)
			active = self.youtube_video_rate.get_active()
		else:
			if self.quality_list:
				active = self.youtube_video_rate.get_active()
            
    def on_youtube_video_rate_changed(self,widget):
		active = self.youtube_video_rate.get_active()
		if self.media_link:
			self.stop_play()
			self.start_play(self.media_link[active])
        
    def start_search(self):
        self.page_index = 0
        self.search_thread_id = thread.start_new_thread(self.analyse_links,())

    def start_stop(self,widget=None):
        url = self.media_link
        if url:
            if self.play_btn.get_label() == "gtk-media-play":
                self.statbar.push(1,"Playing : %s" % self.media_name)
                return self.start_play(url)
            else:
                self.statbar.push(1,"Stopped")
                return self.stop_play(url)

    def start_play(self,url):
        if not sys.platform == "win32":
            self.vis = self.change_visualisation()
            self.visual = gst.element_factory_make(self.vis,'visual')
            self.player.set_property('vis-plugin', self.visual)
        self.play_btn.set_label("gtk-media-stop")
        self.player.set_property("uri", url)
        self.player.set_state(gst.STATE_PLAYING)
        self.play_thread_id = thread.start_new_thread(self.play_thread, ())
        self.is_playing = True

    def stop_play(self,widget=None):
        self.player.set_state(gst.STATE_NULL)
        self.play_btn.set_label("gtk-media-play")
        self.is_playing = False
        self.play_thread_id = None
        self.duration = None
        self.update_time_label()

    def play_thread(self):
        play_thread_id = self.play_thread_id

        while play_thread_id == self.play_thread_id:
            if play_thread_id == self.play_thread_id:
                gtk.gdk.threads_enter()
                self.update_time_label()
                gtk.gdk.threads_leave()
            time.sleep(1)

    def on_message(self, bus, message):
        t = message.type
        if t == gst.MESSAGE_EOS:
            self.play_thread_id = None
            self.player.set_state(gst.STATE_NULL)
            self.play_btn.set_label("gtk-media-play")
            self.check_play_options()
        elif t == gst.MESSAGE_ERROR:
            err, debug = message.parse_error()
            print "Error: %s" % err, debug
            self.play_thread_id = None
            self.player.set_state(gst.STATE_NULL)
            self.play_btn.set_label("gtk-media-play")
            ## continue if continue option selected...
            if self.play_options == "continue":
                self.check_play_options()

    def pause_resume(self,widget):
        if self.pause_btn.get_label() == "gtk-media-pause":
            self.pause_btn.set_label("gtk-media-play")
            self.player.set_state(gst.STATE_PAUSED)
        else:
            self.pause_btn.set_label("gtk-media-pause")
            self.player.set_state(gst.STATE_PLAYING)

    def set_play_options(self,widget):
        wname = widget.name
        wstate = widget.get_active()
        if wname == "continue_checkbox":
            if wstate:
                self.play_options = "continue"
                if self.loop_checkbox.get_active():
                    self.loop_checkbox.set_active(0)
        elif wname == "loop_checkbox":
            if wstate:
                self.play_options = "loop"
                if self.continue_checkbox.get_active():
                    self.continue_checkbox.set_active(0)

    def check_play_options(self):
        if self.play_options == "loop":
            path = self.model.get_path(self.iter)
            if path:
                self.treeview.set_cursor(path)
        elif self.play_options == "continue":
            iter = None
            ## first, check if iter is still available (changed search while
            ## continue mode for exemple..)
            if not self.model.get_path(self.iter) == self.path:
                try:
                    iter = self.model.get_iter_first()
                except:
                    return
                if iter:
                    path = self.model.get_path(iter)
                    self.treeview.set_cursor(path)
                return
            ## check for next iter
            try:
                iter = self.model.iter_next(self.iter)
            except:
                return
            if iter:
                path = self.model.get_path(iter)
                self.treeview.set_cursor(path)
            else:
                if not self.engine == "google.com":
                    ## try changing page
                    self.change_page()
                    ## wait for 10 seconds or exit
                    i = 0
                    while i < 10:
                        try:
                            iter = self.model.get_iter_first()
                        except:
                            continue
                        if iter:
                            path = self.model.get_path(iter)
                            self.treeview.set_cursor(path)
                            break
                        else:
                            i += 1
                            time.sleep(1)
    
    def convert_ns(self, t):
        # This method was submitted by Sam Mason.
        # It's much shorter than the original one.
        s,ns = divmod(t, 1000000000)
        m,s = divmod(s, 60)
        if m < 60:
            return "%02i:%02i" %(m,s)
        else:
            h,m = divmod(m, 60)
            return "%i:%02i:%02i" %(h,m,s)

    def seeker_button_release_event(self, widget, event):  
        value = widget.get_value()
        if self.is_playing == True:
            duration = self.player.query_duration(self.timeFormat, None)[0] 
            time = value * (duration / 100)
            self.player.seek_simple(self.timeFormat, gst.SEEK_FLAG_FLUSH, time)

    def update_time_label(self): 
        """
        Update the time_label to display the current location
        in the media file as well as update the seek bar
        """ 
        if self.is_playing == False:
          adjustment = gtk.Adjustment(0, 0.00, 100.0, 0.1, 1.0, 1.0)
          self.seeker.set_adjustment(adjustment)
          self.time_label.set_text("00:00 / 00:00")
          return False
        
        ## update timer for mini_player and hide it if more than 5 sec 
        ## without mouse movements
        self.timer += 1
        if self.fullscreen == True and self.mini_player == True and self.timer > 5 :
            self.show_mini_player()
        
        if self.duration == None:
          try:
            self.length = self.player.query_duration(self.timeFormat, None)[0]
            self.duration = self.convert_ns(self.length)
          except gst.QueryError:
            self.duration = None
          
        if self.duration != None:
            try:
                self.current_position = self.player.query_position(self.timeFormat, None)[0]
            except gst.QueryError:
                return 0
            current_position_formated = self.convert_ns(self.current_position)
            self.time_label.set_text(current_position_formated + "/" + self.duration)
      
            # Update the seek bar
            # gtk.Adjustment(value=0, lower=0, upper=0, step_incr=0, page_incr=0, page_size=0)
            percent = (float(self.current_position)/float(self.length))*100.0
            adjustment = gtk.Adjustment(percent, 0.00, 100.0, 0.1, 1.0, 1.0)
            self.seeker.set_adjustment(adjustment)
      
        return True
    

    def on_sync_message(self, bus, message):
        if message.structure is None:
            return
        win_id = None
        message_name = message.structure.get_name()
        if message_name == "prepare-xwindow-id":
            if sys.platform == "win32":
                win_id = self.movie_window.window.handle
            else:
                win_id = self.movie_window.window.xid
            gtk.gdk.threads_enter()
            self.sink.set_xwindow_id(win_id)
            gtk.gdk.threads_leave()
            
    def on_drawingarea_clicked(self, widget, event):
        if event.type == gtk.gdk._2BUTTON_PRESS:
            return self.set_fullscreen()
    
    def set_fullscreen(self,widget=None):
        if self.fullscreen :
            self.fullscreen = False
            self.top_infobox.show()
            self.search_box.show()
            self.results_box.show()
            self.statbar.show()
            self.control_box.show()
            self.options_bar.show()
            self.window.window.unfullscreen()
            self.window.set_position(gtk.WIN_POS_CENTER)
        else:
            self.top_infobox.hide()
            self.search_box.hide()
            self.results_box.hide()
            self.options_bar.hide()
            self.window.window.fullscreen()
            self.fullscreen = True
            self.mini_player = True
                
    def on_drawingarea_realized(self, sender):
        if sys.platform == "win32":
            window = self.movie_window.get_window()
            window.ensure_native()
            self.sink.set_xwindow_id(self.movie_window.window.handle)
        else:
            self.sink.set_xwindow_id(self.movie_window.window.xid)
            
    def on_expose_event(self, widget, event):
        x , y, width, height = event.area
        widget.window.draw_drawable(widget.get_style().fg_gc[gtk.STATE_NORMAL],
                                      pixmap, x, y, x, y, width, height)
        return False
        
    def on_configure_event(self, widget, event):
          global pixmap
   
          x, y, width, height = widget.get_allocation()
          pixmap = gtk.gdk.Pixmap(widget.window, width, height)
          pixmap.draw_rectangle(widget.get_style().black_gc,
                                True, 0, 0, width, height)
   
          return True
        
    def on_motion_notify(self, widget, event):
        h=gtk.gdk.screen_height()
        self.timer = 0
        if self.fullscreen and event.y >= h - 10:
            self.show_mini_player()
            time.sleep(0.5)
            
    def show_mini_player(self):
        if self.mini_player == True:
            self.statbar.hide()
            self.control_box.hide()
            self.options_bar.hide()
            self.mini_player = False
        else:
            self.statbar.show()
            self.control_box.show()
            self.mini_player = True
    
    def onKeyPress(self, widget, event):
        key = gtk.gdk.keyval_name(event.keyval)
        if key == 'F2':
            return self.set_fullscreen()

        # If user press Esc button in fullscreen mode
        if event.keyval == gtk.keysyms.Escape and self.fullscreen:
            return self.set_fullscreen()
    
    def on_volume_changed(self, widget, value=10):
        self.player.set_property("volume", float(value)) 
        return True
    
    def set_max_youtube_res(self, widget):
		if widget.get_active():
			self.youtube_max_res = widget.get_child().get_label()
			self.config["youtube_max_res"]=self.youtube_max_res
			## return a dic as conf
			try:
				self.config.write()
			except:
				print "Can't write to the %s config file..." % self.conf_file
		

    def download_file(self,widget):
        if self.engine == "youtube.com":
            media_link = self.media_link[0]
            print "downloading %s" % media_link
            return self.geturl(media_link)
        print "downloading %s" % self.media_link
        return self.geturl(self.media_link)

    def geturl(self,url):
        self.progressbar.show()
        urllib.urlretrieve(url, self.down_dir+"/"+self.media_name,
        lambda nb, bs, fs, url=url: _reporthook(nb,bs,fs,url,self.media_name,self.progressbar))
        gtk.main_iteration()
        self.progressbar.hide()
        
    def on_about_btn_pressed(self, widget):
        dlg = self.gladeGui.get_widget("aboutdialog")
        #dlg.set_version(VERSION)
        response = dlg.run()
        if response == gtk.RESPONSE_DELETE_EVENT or response == gtk.RESPONSE_CANCEL:
            dlg.hide()
            
    def on_settings_btn_pressed(self, widget):
		dlg = self.gladeGui.get_widget("settings_dialog")
		#dlg.set_version(VERSION)
		if self.youtube_max_res == "320x240":
			self.res320.set_active(1)
		elif self.youtube_max_res == "640x320":
			self.res640.set_active(1)
		elif self.youtube_max_res == "854x480":
			self.res854.set_active(1)
		elif self.youtube_max_res == "1280x720":
			self.res1280.set_active(1)
		elif self.youtube_max_res == "1920x1080":
			self.res1920.set_active(1)
		response = dlg.run()
		if response == gtk.RESPONSE_DELETE_EVENT or response == gtk.RESPONSE_CANCEL:
			dlg.hide()

    def exit(self,widget):
        """Stop method, sets the event to terminate the thread's main loop"""
        if self.player.set_state(gst.STATE_PLAYING):
            self.player.set_state(gst.STATE_NULL)
        self.mainloop.quit()

def _GetYoutubeVideoInfo(videoID,eurl=None):
        '''
        Return direct URL to video and dictionary containing additional info
        >> url,info = GetYoutubeVideoInfo("tmFbteHdiSw")
        >>
        '''
        if not eurl:
            params = urllib.urlencode({'video_id':videoID})
        else :
            params = urllib.urlencode({'video_id':videoID, 'eurl':eurl})
        conn = httplib.HTTPConnection("www.youtube.com")
        conn.request("GET","/get_video_info?&%s"%params)
        response = conn.getresponse()
        data = response.read()
        if re.search('status=fail',str(data)):
            return
        video_info = dict((k,urllib.unquote_plus(v)) for k,v in
                                   (nvp.split('=') for nvp in data.split('&')))
        conn.request('GET','/get_video?video_id=%s&t=%s' %
                             ( video_info['video_id'],video_info['token']))
        response = conn.getresponse()
        quality_arr = []
        links_arr = []
        link_list = video_info['fmt_stream_map'].split(",")
        quality_list = video_info['fmt_map'].split(",")
        ## remove flv links...
        i = 0
        for quality in quality_list:
            codec = _get_codec(quality)
            if codec == "flv" and quality.split("/")[1] == "320x240" and re.search("18/320x240",str(quality_list)):
                i+=1
                continue
            elif codec == "flv" and quality.split("/")[1] != "320x240":
				i+=1
				continue
            else:
                links_arr.append(link_list[i].split("|")[1])
                quality_arr.append(quality.split("/")[1] + "|%s" % codec)
                i+=1
        return video_info,links_arr,quality_arr

def _get_codec(num):
    codec=None
    if re.match('5|34|35',num):
        codec = "flv"
    elif re.match('18|22|37|38',num):
        codec= "mp4"
    elif re.match('43|45',num):
        codec= "webm"
    elif re.match('17',num):
        codec= "3gp"
    return codec

def _reporthook(numblocks, blocksize, filesize, url, name, progressbar):
        #print "reporthook(%s, %s, %s)" % (numblocks, blocksize, filesize)
        #XXX Should handle possible filesize=-1.
    if filesize == -1:
        progressbar.set_text("Downloading %-66s" % name)
        progressbar.set_pulse_step(0.2)
        progressbar.pulse()
        gtk.main_iteration()
        time.sleep(0.05)
    else:
        if numblocks != 0:
            try:
                percent = min((numblocks*blocksize*100)/filesize, 100)
            except:
                percent = 100
            if percent < 100:
                time.sleep(0.005)
                progressbar.set_text("Downloading %-66s%3d%% done" % (name, percent))
                progressbar.set_fraction(percent/100.0)
                gtk.main_iteration_do(False)
            else:
                progressbar.hide()
                return
    return

try:
  from xml.etree import cElementTree as ElementTree
except ImportError:
  try:
    import cElementTree as ElementTree
  except ImportError:
    from elementtree import ElementTree


class YouTubeClient:

    users_feed = "http://gdata.youtube.com/feeds/users"
    std_feeds = "http://gdata.youtube.com/feeds/standardfeeds"
    video_name_re = re.compile(r', "t": "([^"]+)"')
    
    def _request(self, feed, *params):
        service = gdata.service.GDataService(server="gdata.youtube.com")
        return service.Get(feed % params)
    
    def search(self, query, page_index, params):
        url = "http://gdata.youtube.com/feeds/api/videos?q=%s&start-index=%s&max-results=25%s" % (query, page_index, params)
        return self._request(url).entry

    def get_thumbnails(self, video):
        doc = video._ToElementTree()
        urls = {}
        for c in doc.findall(".//{http://search.yahoo.com/mrss/}group"):
            for cc in c.findall("{http://search.yahoo.com/mrss/}thumbnail"):
                width = int(cc.get("width"))
                height = int(cc.get("height"))
                size = (width, height)
                url = cc.get("url")
                if size not in urls:
                    urls[size] = [url,]
                else:
                    urls[size].append(url)
        return urls

    def get_largest_thumbnail(self, video):
        thumbnails = self.get_thumbnails(video)
        sizes = thumbnails.keys()
        sizes.sort()
        return thumbnails[sizes[-1]][0]



if __name__ == "__main__":
    GsongFinder()
