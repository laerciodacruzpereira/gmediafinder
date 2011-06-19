import re
import urllib2
import gobject,glib
import json

try:
    from functions import *
except:
    from GmediaFinder.functions import *

class DailyMotion(object):
    def __init__(self,gui):
        self.gui = gui
        self.name = 'DailyMotion'
        self.type = "video"
        self.options_dic = {}
        self.current_page = 1
        self.main_start_page = 1
        self.thread_stop=False
        self.search_url = 'https://api.dailymotion.com/videos?sort=%s&page=%s&limit=25&search=%s&fields=embed_url,thumbnail_medium_url,title'
        self.start_engine()
    
    def start_engine(self):
        self.gui.engine_list[self.name] = ''
    
    def load_gui(self):
        options = {_("Order by: "):{_("Most relevant"):"relevance",_("Most recent"):"recent",_("Most viewed"):"visited",_("Most rated"):"rated"}}
        self.orderby = create_comboBox(self.gui, options)
        filters = {_("Filters: "):{_("HD"):"hd"}}
        self.filters = create_comboBox(self.gui, filters)
        
    def get_search_url(self,query,page):
        choice = self.orderby.getSelected()
        orderby = self.orderbyOpt[choice]
        print self.search_url % (orderby,page,query)
        return self.search_url % (orderby,page,query)
    
    def play(self,link):
        try:
            data = get_url_data(link)
            data = urllib2.urlopen(link)
            j_data = data.read().split('info =')[1].split(';')[0]
            js = json.loads(j_data)
            link = js['stream_url']
            self.gui.media_link = link
            return self.gui.start_play(link)
        except:
            return
        
    def filter(self,data,user_search):
        js = json.load(data)
        l = js['list']
        for dic in l:
            #print dic
            if self.thread_stop == True:
                break
            title = dic['title']
            link = dic['embed_url']
            img_link = dic['thumbnail_medium_url']
            img = download_photo(img_link)
            title = glib.markup_escape_text(title)
            markup = "<small><b>%s</b></small>" % title
            gobject.idle_add(self.gui.add_sound, title, markup, link, img, None, self.name)
        if js['has_more'] != 'true':
            self.print_info(_("%s: No more results for %s...") % (self.name,user_search))
            time.sleep(5)
        self.thread_stop=True
        
    
    def print_info(self,msg):
        gobject.idle_add(self.gui.info_label.set_text,msg)
