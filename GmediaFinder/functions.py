#-*- coding: UTF-8 -*-
import os
import gtk
import time
import re
import urllib2
import urllib
import threading
import time
import gobject
import tempfile

import sys
from time import sleep
from threading import Thread
from urllib import urlretrieve

import HTMLParser
import htmlentitydefs
import htmllib

HTMLParser.attrfind = re.compile(r'\s*([a-zA-Z_][-.:a-zA-Z_0-9]*)(\s*=\s*'r'(\'[^\']*\'|"[^"]*"|[^\s>^\[\]{}\|\'\"]*))?')

def get_url_data(url):
        user_agent = 'Mozilla/5.0 (X11; U; Linux i686; en-US) AppleWebKit/534.15 (KHTML, like Gecko) Ubuntu/10.10 Chromium/10.0.608.0 Chrome/10.0.608.0 Safari/534.15'
        headers =  { 'User-Agent' : user_agent , 'Accept-Language' : 'fr-FR,fr;q=0.8,en-US;q=0.6,en;q=0.4' }
        ## start the request
        try:
            req = urllib2.Request(url,None,headers)
        except:
            return
        try:
            data = urllib2.urlopen(req)
        except:
            return

        return data
        
def download_photo(img_url):
    filename = os.path.basename(img_url)
    if sys.platform == "win32":
        file_path = os.path.join(tempfile.gettempdir(), filename)
    else:
        file_path = "/tmp/%s" % filename
    if os.path.exists(file_path) and not os.path.isdir(file_path):
        os.remove(file_path)
    p = urllib.urlretrieve(img_url, file_path)
    try:
        vid_pic = gtk.gdk.pixbuf_new_from_file_at_scale(p[0],100,100,1)
        return vid_pic
    except:
        return None

def with_lock(func, args):
		gtk.gdk.threads_enter()
		try:
			return func(*args)
		finally:
			gtk.gdk.threads_leave()

def calc_eta(start, now, total, current):
		if total is None:
			return '--:--'
		dif = now - start
		if current == 0 or dif < 0.001: # One millisecond
			return '--:--'
		rate = float(current) / dif
		eta = long((float(total) - float(current)) / rate)
		(eta_mins, eta_secs) = divmod(eta, 60)
		if eta_mins > 99:
			return '--:--'
		values = {'min': eta_mins, 'sec': eta_secs}
		return _('Remaining : %(min)02d:%(sec)02d') % values

		
def yesno(title,msg):
    dialog = gtk.MessageDialog(parent = None,
    buttons = gtk.BUTTONS_YES_NO,
    flags =gtk.DIALOG_DESTROY_WITH_PARENT,
    type = gtk.MESSAGE_QUESTION,
    message_format = msg
    )
    dialog.set_position("center")
    dialog.set_title(title)
    result = dialog.run()
    dialog.destroy()

    if result == gtk.RESPONSE_YES:
        return "Yes"
    elif result == gtk.RESPONSE_NO:
        return "No"
        
def error_dialog(message, parent = None):
    """
    Displays an error message.
    """

    dialog = gtk.MessageDialog(parent = parent, type = gtk.MESSAGE_ERROR, buttons = gtk.BUTTONS_OK, flags = gtk.DIALOG_MODAL)
    dialog.set_markup(message)
    dialog.set_position('center')

    result = dialog.run()
    dialog.destroy()

def sortDict(d):
    """ Returns the keys of dictionary d sorted by their values """
    items=d.items()
    backitems=[ [v[1],v[0]] for v in items]
    backitems.sort()
    return [ backitems[i][1] for i in range(0,len(backitems))]

def create_comboBox(gui=None,dic=None):
    model = gtk.ListStore(str,gtk.gdk.Color)
    combobox = gtk.ComboBox(model)
    cell = gtk.CellRendererText()
    combobox.pack_start(cell, True)
    combobox.add_attribute(cell, 'text', 0)
    combobox.add_attribute(cell, 'foreground-gdk', 1)
    cb=None
    
    if dic:
        target = gui.search_opt_box
        for key,values in dic.items():
            label = gtk.Label(key)
            target.pack_start(label,False,False,5)
            cb = ComboBox(combobox)
            dr = sorted(values.keys())
            for val in dr:
                cb.append(val)
            target.add(combobox)
            cb.select(0)
            target.show_all()
        return cb
    return combobox


class ComboBox(object):
    def __init__(self,combobox):
        self.combobox = combobox
        self.model = self.combobox.get_model()

    def append(self,what,warn=False):
        if warn:
            color = gtk.gdk.color_parse("red")
            self.model.append([what, color])
        else:
            self.combobox.append_text(what)

    def remove(self,what):
        self.combobox.remove_text(what)

    def select(self,which):
        self.combobox.set_active(which)

    def getSelectedIndex(self):
        return self.combobox.get_active()

    def getSelected(self):
        return self.model[self.getSelectedIndex()][0]

    def setIndexFromString(self,usr_search):
        found = 0
        for item in self.model:
            iter = item.iter
            path = item.path
            name = self.model.get_value(iter, 0)
            if name == usr_search:
                found = 1
                self.select(path[0])
                break
            self.combobox.set_active(-1)
            
    def get_list(self):
        l = {}
        for item in self.model:
            iter = item.iter
            path = item.path
            name = self.model.get_value(iter, 0)
            if not name == "":
                l[name] = ''
        return l
        

def decode_htmlentities(text):
    p = htmllib.HTMLParser(None)
    p.save_bgn()
    p.feed(text)
    try:
        text = p.save_end().decode('utf-8')
    except:
        return
    text = re.sub('&#_;','\'',text)
    text = re.sub('&# ;','\'',text)
    text = re.sub('&amp;','&',text)
    text = re.sub('_',' ',text)
    return text


# self._hook est appelé à chaque requete urllib
class Abort(Exception):
    pass

class urlFetch(Thread):
    def __init__(self, engine, url, query, page, local=tempfile.NamedTemporaryFile().name):
        Thread.__init__(self)
        self.url = url
        self.stop = False
        self.local = local
        self.engine = engine
        self.query = query
        self.page = page

    def _hook(self, *args):
        if self.stop:
            raise Abort
        #sys.stdout.write('search request stopped: %s,%s' % (self.engine,self.query))
        sys.stdout.flush()

    def run(self):
        if not isinstance(self.url, str):
            try:
                self.engine.filter(self.url,self.query)
            except:
                self.stop = True
                self.abort()
        else:
            try:
                t = urlretrieve(self.url, self.local, self._hook)
                f = open(self.local)
                self.engine.filter(f,self.query)
            except Abort, KeyBoardInterrupt:
                e = sys.exc_info()[1]
                if e != "":
                    print "<p>Error: %s</p>" % e
                print 'Aborted'
            except:
                try:
                    t = urllib2.urlopen(self.url)
                    self.engine.filter(t, self.query)
                except:
                    self.stop = True
                    raise


    def abort(self):
        self.stop = True


def get_redirect_link(link):
    request = urllib2.Request(link)
    opener = urllib2.build_opener()
    f = opener.open(request)
    return f.url

def warn_dialog(dialog):
    result = dialog.run()
    dialog.hide()
    return result
    
    
    
""" Inbox Files Downloader by maris@chown.lv. You are free do whatever You want with this code! """

import urllib2, urllib, cookielib, re, time, optparse, socket, os, sys


""" Poster lib for HTTP streaming upload, taken from http://atlee.ca/software/poster"""

import httplib, urllib2, socket

class FileDownloader(threading.Thread):
    """ Files downloader class """
    createdir = False
    urlopen = urllib2.urlopen
    cj = cookielib.LWPCookieJar()
    Request = urllib2.Request
    
    post_data = None
    download_items = []
    
    localheaders = { 'User-Agent' : 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.0.2) Gecko/2008092313 Ubuntu/8.04 (hardy) Firefox/3.1.6' }
    
    def __init__(self, gui,url, name, pbar, btnf, btn,btn_conv,btnstop,convert,label,btnpause):
        threading.Thread.__init__(self)
        self.label = label
        self.gui = gui
        self._stopevent = threading.Event()
        self.url = url
        ## filenames
        self.encoded_name = name
        self.decoded_name = label
        self.target = os.path.join(self.gui.down_dir,self.decoded_name)
        self.temp_name = self.decoded_name
        self.temp_file = os.path.join(self.gui.down_dir,self.temp_name)
        self.conf_temp_name = '.'+self.decoded_name+'.conf'
        self.conf_temp_file = os.path.join(self.gui.down_dir,self.conf_temp_name)
        # progress bar and buttons
        self.pbar = pbar
        self.btnf = btnf
        self.btn = btn
        self.btn_conv = btn_conv
        self.btnstop = btnstop
        self.btnpause = btnpause
        self.convert_check = convert
        self.btnstop.connect('clicked', self.cancel)
        self.btnpause.connect('clicked', self.pause)
        self.createdir = False
        self.paused = False
        self.canceled = False
        self.localheaders = { 'User-Agent' : 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.0.2) Gecko/2008092313 Ubuntu/8.04 (hardy) Firefox/3.1.6' }
        
    def download(self, url, destination):
        resume = False
        self.paused = False
        req = urllib2.Request(url, headers = self.localheaders)
        response = urllib2.urlopen(req)
        headers = response.info()
        if os.path.isfile(self.target) and float(headers['Content-Length']) == float(os.stat(self.target)[6]):
            os.unlink(self.target)
            self.check_target_file(self.temp_file)
        elif os.path.isfile(self.temp_file):
            gobject.idle_add(self.pbar.set_text,_("File is here but seems to be incomplete!"))
            size_local = float(os.stat(self.temp_file)[6])
            size_on_server = float(headers['Content-Length'])
            if headers['Accept-Ranges'] == 'bytes':
                gobject.idle_add(self.pbar.set_text,_("Range request supported, trying to resume..."))
                try:
                    req = urllib2.Request(url, headers = self.localheaders)
                    req.add_header("range", "bytes=%d-%d"%(size_local,size_on_server))
                    response = urllib2.urlopen(req)
                    resume = True
                except:	
                    resume = False
                    self.temp_file += '.duplicate'
                    return False
            else:
                gobject.idle_add(self.pbar.set_text,_("Range request not supported, redownloading file"))
                os.unlink(self.temp_file)
                return False
        try:
            f = open(self.temp_file, "ab")
        except IOError, errmsg:
            if not os.path.exists(self.temp_file):
                f = open(self.temp_file, "wb")
            else:
                print "%s" %(errmsg)
                response.close()
                return False
    
        try:
            if resume:
                current_bytes = size_local
            else:
                current_bytes = 0
            while True:
                try:
                    if self._stopevent.isSet():
                        gobject.idle_add(self.pbar.set_text,_("download stopped..."))
                        break
                    read_start = time.time()
                    if not self.paused:
                        bytes = response.read(1024000)
                        current_bytes += 1024000
                        time_diff = time.time() - read_start
                        if time_diff == 0:
                            time_diff = 1
                        troughput = round((float(1024000/time_diff)/1024)/1024*1024,2)
                        procents = int((float(current_bytes)/float(headers['Content-Length']))*100)
                        length = round((float(int(headers['Content-Length'])/1024))/1024,2)
                        current = round((float(current_bytes/1024))/1024,2)
                        if procents < 100 and not self.paused:
                            gobject.idle_add(self.pbar.set_text,"%3d%% %s of %s Mb at %s Ko/s" % (procents, current, length,
                                                                            troughput))
                            gobject.idle_add(self.pbar.set_fraction,procents/100.0)
                        elif procents == 100:
                            gobject.idle_add(self.pbar.set_text,_("Download complete"))
                            gobject.idle_add(self.pbar.set_fraction,100/100.0)
                        f.write(bytes)
                    else:
                        sleep(1)
                except IOError, (errno, strerror):
                    print "I/O error(%s): %s" % (errno, strerror)
                if bytes == "":
                    print "%s Finished" % (self.target)
                    gtk.gdk.threads_enter()
                    os.unlink(self.conf_temp_file)
                    gtk.gdk.threads_leave()
                    break
            sys.stdout.write("\n")
        except KeyboardInterrupt, errmsg:
            print "KeyboardInterrupt Caught: %s" % (errmsg)
            print "Cleaning up"
            f.close()
            response.close()
        f.close()
        response.close()
        return True
    
        
    def run(self):
        gobject.idle_add(self.pbar.set_text,_("Starting download..."))
        while not self._stopevent.isSet():
            self.gui.active_downloads += 1
            gobject.idle_add(self.gui.active_down_label.set_text,str(self.gui.active_downloads))
            ## download...
            try:
                #start_time = time.time()
                self.check_target_file(self.temp_file)
                #req = urllib2.Request(self.url)
                #response = urllib2.urlopen(req)
                #response.close()
                self.download(self.url, self.temp_file)
                gobject.idle_add(self.btnf.show)
                if self.convert_check == 'True' and not self.canceled:
                    gobject.idle_add(self.btn_conv.show)
                gobject.idle_add(self.btn.show)
                gobject.idle_add(self.btnstop.hide)
                gobject.idle_add(self.btnpause.hide)
                self.decrease_down_count()
                if self.canceled:
                    gobject.idle_add(self.pbar.set_text,_("Download canceled..."))
                else:
                    self._stopevent.set()
                    gobject.idle_add(self.pbar.set_text,_("Download complete"))
                gobject.idle_add(self.pbar.set_fraction,100/100.0)
            except KeyboardInterrupt, errmsg:
                gobject.idle_add(self.pbar.set_text,_("Failed..."))
                gobject.idle_add(self.btn.show)
                self.decrease_down_count()
                gobject.idle_add(self.btnstop.hide)
                gobject.idle_add(self.btnpause.hide)
                self._stopevent.set()
            
    def check_target_file(self,tmp_file):
        if not os.path.exists(self.conf_temp_file):
            f = open(self.conf_temp_file,'w')
            f.write(self.url)
            f.close()
        else:
            f = open(self.conf_temp_file,'r')
            self.url = f.read()
            f.close()
            
    def cancel(self,widget):
        self.canceled = True
        gobject.idle_add(self.pbar.set_text,_("Cancel downloading..."))
        self._stopevent.set()
        self.decrease_down_count()
        os.unlink(self.temp_file)
        os.unlink(self.conf_temp_file)
        
    def stop(self,widget=None):
        self._stopevent.set()
    
    def pause(self,widget):
        if not self.paused:
            self.paused = True
            gobject.idle_add(self.pbar.set_text,_("download paused..."))
            self.decrease_down_count()
        else:
            self.paused = False
            self.increase_down_count()
            gobject.idle_add(self.pbar.set_text,_("Resuming download..."))
    
    def decrease_down_count(self):
        if self.gui.active_downloads > 0:
            self.gui.active_downloads -= 1
            gobject.idle_add(self.gui.active_down_label.set_text,str(self.gui.active_downloads))
            
    def increase_down_count(self):
        if self.gui.active_downloads > 0:
            self.gui.active_downloads += 1
            gobject.idle_add(self.gui.active_down_label.set_text,str(self.gui.active_downloads))
    
