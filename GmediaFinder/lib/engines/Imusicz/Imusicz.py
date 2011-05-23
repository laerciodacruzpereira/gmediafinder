
import re
import urllib
import socket
from BeautifulSoup import BeautifulSoup, NavigableString, BeautifulStoneSoup

try:
	from functions import *
except:
	from GmediaFinder.functions import *

class Imusicz(object):
    def __init__(self,gui):
        self.gui = gui
        self.name="Imusicz"
        self.current_page = 1
        self.main_start_page = 1
        self.search_url = "http://imusicz.net/search/mp3/%s/%s.html"
        self.start_engine()


    def start_engine(self):
		self.gui.engine_list[self.name] = ''

    def filter(self, url): 
        soup = self.parser.parse(self.browser.open(url))
        vid_list = []
        for l in soup.findAll('a', href=True):
			try:
			    u = re.search('/watch/.*"',str(l)).group(0)
			    vid_list.append(u)
			except:
				continue
				
        imglist = soup.findAll('img',attrs={'class': 'video-thumb'})
        img_list = []
        for t in imglist:
            img = t.attrMap['src']
            img_list.append(img)
        return self.uniq(vid_list), img_list
        
    def search(self, query, page=1):
		timeout = 30
		socket.setdefaulttimeout(timeout)
		data = get_url_data(self.search_url % (page, urllib.quote(query)))
		return self.filter(data,query)
		
    def filter(self,data,user_search):
		if not data:
			print "timeout..."
			return
		soup = BeautifulStoneSoup(data.decode('utf-8'),selfClosingTags=['/>'])
		nlist = []
		link_list = []
		next_page = 1
		pagination_table = soup.find('table',attrs={'class':'pagination'})
		if pagination_table:
			next_check = pagination_table.findAll('a')
			for a in next_check:
				l = str(a.string)
				if l == "Next":
					next_page = 1
			if next_page:
				self.gui.informations_label.set_text(_("Results page %s for %s...(Next page available)") % (self.current_page, user_search))
				self.current_page += 1
				self.gui.changepage_btn.show()
				self.gui.search_btn.set_sensitive(1)
				self.gui.changepage_btn.set_sensitive(1)
			else:
				self.gui.changepage_btn.hide()
				self.current_page = 1
				self.gui.informations_label.set_text(_("no more files found for %s...") % (user_search))
				self.gui.search_btn.set_sensitive(1)
				return

		flist = soup.findAll('td',attrs={'width':'75'})
		if len(flist) == 0:
			self.gui.changepage_btn.hide()
			self.gui.informations_label.set_text(_("no files found for %s...") % (self.user_search))
			self.gui.search_btn.set_sensitive(1)
			return
		for link in flist:
			try:
				furl = re.search('a href="(http(\S.*)(.mp3|.mp4|.ogg|.aac|.wav|.wma|.wmv|.avi|.mpeg|.mpg|.ogv)(\S.*)redirect)"(\S.*)Download',str(link)).group(1)
				name = re.search('name=(\S.*)(.mp3|.mp4|.ogg|.aac|.wav|.wma|.wmv|.avi|.mpeg|.mpg|.ogv)',str(furl)).group(1)
				linkId= re.search('url=(\S.*)&amp',str(furl)).group(1)
				link = urllib2.unquote('http://imusicz.net/download.php?url='+linkId)
				name = BeautifulStoneSoup(name, convertEntities=BeautifulStoneSoup.HTML_ENTITIES)
				nlist.append(name)
				link_list.append(link)
			except:
				continue
		## add to the treeview if ok
		i = 0
		for name in nlist:
			if name and link_list[i]:
				self.gui.add_sound(name, link_list[i])
				i += 1

