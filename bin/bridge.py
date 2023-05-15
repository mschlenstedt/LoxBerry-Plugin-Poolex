#!/usr/bin/python3
# -*- coding: utf-8 -*-

import tinytuya
import paho.mqtt.client as mqtt
import json
import logging
import os
import sys
from datetime import datetime
import getopt
import time
import signal
import copy

# Basic needed vars
verbose=0
pconfig = dict()
tconfig = dict()
dconfig = dict()
devices = dict()
mqttconfig = dict()
deviceid = "";
devicekey = "";
devicename = "";
deviceproductname = "";

# Plugin Vars
lbpconfigdir = os.popen("perl -e 'use LoxBerry::System; print $lbpconfigdir; exit;'").read()
lbpdatadir = os.popen("perl -e 'use LoxBerry::System; print $lbpdatadir; exit;'").read()
lbplogdir = os.popen("perl -e 'use LoxBerry::System; print $lbplogdir; exit;'").read()

#############################################################################
# MQTT Lib functions
#############################################################################

def on_connect(client, userdata, flags, rc):
	if rc==0:
		client.connected_flag=True #set flag
		log.info("MQTT: Connected OK")
		client.publish(topic + "/running", str("1"), retain=1)
	else:
		log.critical("MQTT: Bad connection, Returned code=",rc)

def on_message(client, userdata, message):
	q.put(message)

#############################################################################
# Plugin Lib functions
#############################################################################

def readpconfig():
	try:
		with open(lbpconfigdir + '/pluginconfig.json') as f:
			global pconfig
			pconfig = json.load(f)

		if str(pconfig['topic']) == "":
			log.warning("MQTT Topic is not set. Set it to default topic 'poolex'.")
			pconfig['topic'] = "poolex"
	except:
		log.critical("Cannot read plugin configuration")
		sys.exit(2)

def readtconfig():
	try:
		with open(lbpconfigdir + '/tinytuya.json') as f:
			global tconfig
			tconfig = json.load(f)
		if str(tconfig['apiKey']) == "":
			log.error("apiKey not defined.")
			sys.exit(2)
		if str(tconfig['apiSecret']) == "":
			log.error("apiSecret not defined.")
			sys.exit(2)
		if str(tconfig['apiRegion']) == "":
			log.error("apiRegion not defined.")
			sys.exit(2)
		if str(tconfig['apiDeviceID']) == "":
			log.error("apiDevice not defined.")
			sys.exit(2)
		if str(tconfig['type']) == "":
			log.error("type not defined.")
			sys.exit(2)
	except:
		log.critical("Cannot read tinytuya configuration")
		sys.exit(2)
	try:
		with open(lbpconfigdir + '/devices/' + tconfig['type'] + '.json') as f:
			global dconfig
			dconfig = json.load(f)
	except:
		log.critical("Cannot read device configuration " + tconfig['type'] + ".json")
		sys.exit(2)

def readdevices():
	try:
		with open(lbpconfigdir + '/devices.json') as f:
			global devices
			devices = json.load(f)
	except:
		log.critical("Cannot read devices file")
		sys.exit(2)

def exit_handler(a="", b=""):
	# Close MQTT
	client.loop_stop()
	log.info("MQTT: Disconnecting from Broker.")
	client.publish(topic + "/running", str("0"), retain=1)
	client.disconnect()
	# close the log
	if str(logdbkey) != "":
		logging.shutdown()
		os.system("perl -e 'use LoxBerry::Log; my $log = LoxBerry::Log->new ( dbkey => \"" + logdbkey + "\", append => 1 ); LOGEND \"Good Bye.\"; $log->close; exit;'")
	else:
		log.info("Good Bye.")
	# End
	sys.exit();

#############################################################################
#  Main program
#############################################################################

# Standard loglevel
loglevel="ERROR"
logfile=""
logdbkey=""

# Get full command-line arguments
# https://stackabuse.com/command-line-arguments-in-python/
full_cmd_arguments = sys.argv
argument_list = full_cmd_arguments[1:]
short_options = "vlfd:"
long_options = ["verbose","loglevel=","logfile=","logdbkey="]

try:
	arguments, values = getopt.getopt(argument_list, short_options, long_options)
except getopt.error as err:
	print (str(err))
	sys.exit(2)

for current_argument, current_value in arguments:
	if current_argument in ("-v", "--verbose"):
		loglevel="DEBUG"
		verbose=1
	elif current_argument in ("-l", "--loglevel"):
		loglevel=current_value
	elif current_argument in ("-f", "--logfile"):
		logfile=current_value
	elif current_argument in ("-d", "--logdbkey"):
		logdbkey=current_value

# Logging with standard LoxBerry log format
numeric_loglevel = getattr(logging, loglevel.upper(), None)
if not isinstance(numeric_loglevel, int):
	raise ValueError('Invalid log level: %s' % loglevel)

if str(logfile) == "":
	logfile = str(lbplogdir) + "/" + datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')[:-3] + "_tuya-bridge.log"

log = logging.getLogger()
fileHandler = logging.FileHandler(logfile)
formatter = logging.Formatter('%(asctime)s.%(msecs)03d <%(levelname)s> %(message)s',datefmt='%H:%M:%S')

if verbose == 1:
	streamHandler = logging.StreamHandler(sys.stdout)
	streamHandler.setFormatter(formatter)
	log.addHandler(streamHandler)

fileHandler.setFormatter(formatter)
log.addHandler(fileHandler)

# Logging Starting message
log.setLevel(logging.INFO)
log.info("Starting Logfile for Tuya Bridge. The Loglevel is %s" % loglevel.upper())
log.setLevel(numeric_loglevel)

# Read MQTT config
mqttconfig = dict()
mqttconfig['server'] = os.popen("perl -e 'use LoxBerry::IO; my $mqttcred = LoxBerry::IO::mqtt_connectiondetails(); print $mqttcred->{brokerhost}; exit'").read()
mqttconfig['port'] = os.popen("perl -e 'use LoxBerry::IO; my $mqttcred = LoxBerry::IO::mqtt_connectiondetails(); print $mqttcred->{brokerport}; exit'").read()
mqttconfig['username'] = os.popen("perl -e 'use LoxBerry::IO; my $mqttcred = LoxBerry::IO::mqtt_connectiondetails(); print $mqttcred->{brokeruser}; exit'").read()
mqttconfig['password'] = os.popen("perl -e 'use LoxBerry::IO; my $mqttcred = LoxBerry::IO::mqtt_connectiondetails(); print $mqttcred->{brokerpass}; exit'").read()

if mqttconfig['server'] == "" or mqttconfig['port'] == "":
	log.critical("Cannot find mqtt configuration")
	sys.exit(2)

# Read Plugin config
readpconfig()
readtconfig()
readdevices()

# Main Topic
topic = pconfig['topic']
mqttpause = 0 # Just in Case we need a slow down...

# Conncect to broker
client = mqtt.Client()
client.will_set(topic + "/running", str("0"), 0, True)
client.connected_flag=False
client.on_connect = on_connect

if mqttconfig['username'] and mqttconfig['password']:
	log.info("Using MQTT Username and password.")
	client.username_pw_set(username = mqttconfig['username'],password = mqttconfig['password'])

log.info("Connecting to Broker %s on port %s." % (mqttconfig['server'], str(mqttconfig['port'])))
client.connect(mqttconfig['server'], port = int(mqttconfig['port']))

# Subscribe to the set/comand topic
stopic = topic + "/set"
client.subscribe(stopic, qos=0)
client.on_message = on_message

# Start MQTT Loop
client.loop_start()

# Wait for connection
counter=0
while not client.connected_flag: #wait in loop
	log.info("MQTT: Wait for connection...")
	time.sleep(1)
	counter+=1
	if counter > 60:
		log.critical("MQTT: Cannot connect to Broker %s on port %s." % (mqttconfig['server'], str(mqttconfig['port'])))
		sys.exit(2)

# Exit handler
#atexit.register(exit_handler)
signal.signal(signal.SIGTERM, exit_handler)
signal.signal(signal.SIGINT, exit_handler)

# Find Device
for i in devices:
	if i['id'] == tconfig['apiDeviceID']:
		deviceid = i['id']
		devicekey = i['key']
		devicename = i['name']
		devicenversion = i['version']
		deviceproductname = i['product_name']
		break

if devicekey == "":
	log.critical("Cannot find Device Key for %s." % (tconfig['apiDeviceID']))
	sys.exit(2)

# Create socket to device
d = tinytuya.OutletDevice(deviceid, 'Auto', devicekey)
d.set_socketPersistent(True)

# Get status
log.info("Send Request for Status")
payload = d.generate_payload(tinytuya.DP_QUERY)
d.send(payload)
cdata = d.receive()
while cdata is None: #wait in loop
	log.info("Wait for first status data set...")
	d.send(payload)
	cdata = d.receive()
	time.sleep(1)
	counter+=1
	if counter > 60:
		log.critical("Cannot get first status data set.")
		sys.exit(2)
log.info('Complete received Payload: %r' % cdata)
send = copy.deepcopy(cdata)
keysList = list(send['dps'].keys())
for i in keysList:
	newname = ""
	for j in dconfig['primary_entity']['dps']:
		if str(j['id']) == str(i):
			newname = j['name']
			break
	if newname != "":
		send['dps'][newname] = send['dps'].pop(i)
log.info('Complete data to send: %r' % send)
log.info('Raw Complete data to send: %r' % cdata)
client.publish(topic + "/status", json.dumps(send), retain=1)
client.publish(topic + "/status_raw", json.dumps(cdata), retain=1)
client.publish(topic + "/last", str(int(time.time())), retain=1)

#
# Loop
#

log.info("Begin Monitor Loop")
while(True):
	# See if any data is available
	data = d.receive()
	log.info('Received Payload: %r' % data)
	if data is not None:
		keysList = list(data['dps'].keys())
		for i in keysList:
			cdata['dps'][i] = data['dps'][i]
		log.info('Complete received Payload: %r' % cdata)
		send = copy.deepcopy(cdata)
		keysList = list(send['dps'].keys())
		for i in keysList:
			newname = ""
			for j in dconfig['primary_entity']['dps']:
				if str(j['id']) == str(i):
					newname = str(j['name'])
					break
			if newname != "":
				send['dps'][newname] = send['dps'].pop(i)
		log.info('Complete data to send: %r' % send)
		client.publish(topic + "/status", json.dumps(send), retain=1)
		client.publish(topic + "/last", str(data['t']), retain=1)

	# Send keyalive heartbeat
	log.info("Send Heartbeat Ping")
	payload = d.generate_payload(tinytuya.HEART_BEAT)
	d.send(payload)
