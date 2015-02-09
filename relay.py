# -*- coding: utf-8 -*-
import argparse
import random
import os
import time
import datetime
import threading
import signal
import sys
import RPi.GPIO as GPIO
import cherrypy
import json
import urlparse
from ws4py.server.cherrypyserver import WebSocketPlugin, WebSocketTool
from ws4py.websocket import WebSocket
from ws4py.messaging import TextMessage

class ChatWebSocketHandler(WebSocket):
	def received_message(self, m):
		msg=m.data.decode("utf-8")
		try:
			jo=json.loads(msg)
		except(ValueError, KeyError, TypeError):
			cherrypy.log("Not Json");
		cmd=jo["c"]
		if (cmd=="update"):
			readJsonLabels()
			self.send(jsonLabels)
		elif(cmd=="on"):
			r=int(jo["r"])
			GPIO.output(ALL_CH[r-1],GPIO.LOW)
			print "On:",r-1
		elif(cmd=="off"):
			r=int(jo["r"])
			GPIO.output(ALL_CH[r-1],GPIO.HIGH)
			print "Off:",r-1
		else:
			cherrypy.log("Not a command");
		#self.send(statusJSON(getStatus()))
		cherrypy.engine.publish('websocket-broadcast', statusJSON(getStatus()))

	def closed(self, code, reason="A client left the room without a proper explanation."):
		cherrypy.engine.publish('websocket-broadcast', TextMessage(reason))

class Root(object):
    def __init__(self, host, port, ssl=False):
        self.host = host
        self.port = port
        self.scheme = 'wss' if ssl else 'ws'

    @cherrypy.expose
    def index(self):
        urlP=urlparse.urlparse(cherrypy.request.base);
        fo=open('index.html')
        content=fo.read()
        fo.close()
        return content

    @cherrypy.expose
    def ws(self):
        cherrypy.log("Handler created: %s" % repr(cherrypy.request.ws_handler))

def getStatus():
	return [GPIO.input(CH1),\
			GPIO.input(CH2),\
			GPIO.input(CH3),\
			GPIO.input(CH4),\
			GPIO.input(CH5),\
			GPIO.input(CH6),\
			GPIO.input(CH7),\
			GPIO.input(CH8)]

def statusJSON(status):
	return '{"status":['+(', '.join(str(x) for x in status))+']}';

def stpoll(arg):
	global pollStatus, oldStatus, currentStatus
	while pollStatus:
		if 'WebSocket' in globals():
			currentStatus=getStatus()
			STATUS=statusJSON(currentStatus)
			if oldStatus!=currentStatus:
				cherrypy.engine.publish('websocket-broadcast', '%s ' %STATUS)
			oldStatus=currentStatus
		time.sleep(2)
	cherrypy.log("exitting therad");

def timing(arg):
	# read from json timing file and switch tho lights on / off based on the time of the day.
	global jsonLabels
	while pollStatus:
		data = json.loads(jsonLabels);
		time.sleep(3)
	return 0;

def signal_handler(signal, frame):
	# read from keyb for ctrl + c
	global pollStatus
	pollStatus=False
	cherrypy.engine.stop()
	cherrypy.engine.exit()
	cherrypy.log('You pressed Ctrl+C!')

def readJsonLabels():
	# Read 
	global jsonLabels
	fo=open('relayLabel.json')
	jsonLabels=fo.read()
	fo.close()

def time_in_range(start, end, x):
    """Return true if x is in the range [start, end]"""
    if start <= end:
        return start <= x <= end
    else:
        return start <= x or x <= end

GPIO.setmode(GPIO.BOARD)
CH1=11
CH2=12
CH3=13
CH4=15
CH5=16
CH6=18
CH7=22
CH8=7
ALL_CH=(CH1,CH2,CH3,CH4,CH5,CH6,CH7,CH8)
GPIO.setup(ALL_CH, GPIO.OUT)
GPIO.output(ALL_CH,GPIO.HIGH)
currentStatus=[1,1,1,1,1,1,1,1]
oldStatus=[0,0,0,0,0,0,0]
jsonLabels="{}"
readJsonLabels()

if __name__ == '__main__':
  import logging
  from ws4py import configure_logger
  print os.path.abspath(os.path.join(os.path.dirname(__file__), 'static'))
  configure_logger(level=logging.DEBUG)
  signal.signal(signal.SIGINT, signal_handler)
  pollStatus=True 
  thread = threading.Thread(target = stpoll, args = (10, ))
  thread.daemon = True
  thread2 = threading.Thread(target = timing, args = (10, ))
  thread2.daemon = True
  thread2.start()
  thread.start()
  parser = argparse.ArgumentParser(description='Echo CherryPy Server')
  parser.add_argument('--host', default='0.0.0.0')
  parser.add_argument('-p', '--port', default=9000, type=int)
  parser.add_argument('--ssl', action='store_true')
  args = parser.parse_args()

  cherrypy.config.update({'server.socket_host': args.host,
                          'server.socket_port': args.port,
                          'tools.staticdir.root': os.path.abspath(os.path.join(os.path.dirname(__file__), 'static'))})

  if args.ssl:
      cherrypy.config.update({'server.ssl_certificate': './server.crt',
                              'server.ssl_private_key': './server.key'})

  WebSocketPlugin(cherrypy.engine).subscribe()
  cherrypy.tools.websocket = WebSocketTool()
  pwd=os.getcwd();
  cherrypy.quickstart(Root(args.host, args.port, args.ssl), '', config={
  		'/': {
  			'tools.staticdir.on': True,
			'tools.staticdir.dir': ''
  		},
		'/ws': {
			'tools.websocket.on': True,
			'tools.websocket.handler_cls': ChatWebSocketHandler
		  },
		'/js': {
			'tools.staticdir.on': True,
			'tools.staticdir.dir': 'js'
		  },
		'/fonts': {
			'tools.staticdir.on': True,
			'tools.staticdir.dir': 'fonts'
		  }
  	});
  thread.join();
  GPIO.cleanup();
