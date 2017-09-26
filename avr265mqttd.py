#!/usr/bin/python

# This program as it stands controls a Harman Kardon AVR265 receiver over RS-232 on /dev/ttyUSB0.
# Make sure the receiver has 'RS-232 Control' set to 'On' in the main menu.
# based on various scripts around the internet

import serial
import time
import binascii
import paho.mqtt.client as paho

import time
from sys import argv
from opcodes import CmdMsg,CmdAck
from pprint import pprint
import datetime
import struct


port='/dev/ttyUSB0'
ser = serial.Serial()
ser.port = port
ser.baudrate = 57600                # found after exhaustive testing, FUCK
ser.bytesize = serial.EIGHTBITS     #number of bits per bytes
ser.parity = serial.PARITY_NONE     #set parity check: no parity
ser.stopbits = serial.STOPBITS_ONE  #number of stop bits
try:
    ser.open()
except Exception, msg:
    print ':: error open serial port: ', msg
    exit()



def readAVR(ser):
    while (ser.inWaiting()>9):
        data=ser.read(ser.inWaiting())
        for val in [x for x in data.split("AVRACK") if x]:
            for k,v in CmdAck.iteritems():
                if val.startswith(k):
                    if v == "VOL_TOG_ACK":
                        vol=struct.unpack("<b", val[3:])[0] - 34
                        client.publish("stat/AVR/VOL",vol, qos=0, retain=True)
                    if isinstance(v, dict):
                        for k2,v2 in v.iteritems():
                            client.publish("stat/AVR/%s" % k2,v2, qos=0, retain=True)


def sendAVR(command,ser):
    if ser.isOpen():
        try:
            ser.flushOutput()#flush output buffer, aborting current output
            ser.write('PCSEND\x02\x04'+command)
            time.sleep(0.1)  #give the serial port some time
        except Exception, msg:
            print ':: error communicating...:',msg
    else:
        print ':: cannot open serial port'

def on_connect(client, userdata, rc):
    print("Connected with result code "+str(rc))
    client.subscribe("cmnd/AVR/#")
    client.publish("tele/AVR/TIME",datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%dT%H:%M:%S'))


def on_message(client, userdata, msg):
    global lockser
    global ser
    lockser=1
    print(msg.topic+" "+str(msg.payload))
    tmp=msg.topic.split("/")
    command=tmp[len(tmp)-1]
    print "command:%s" % command
    print "payload:%s" % msg.payload
    try:
        if isinstance(CmdMsg[command], dict):
            sendAVR(CmdMsg[command][msg.payload],ser)
        else:
            sendAVR(CmdMsg[command],ser)
    except KeyError:
        if (command == "SET_VOL"):
            vol=int(msg.payload)
            if vol < 0:
                vol=0
            if vol > 50:
                vol=50
            print "vol:%i" % vol
            sendAVR('\x80\x70\x00\x00\x02%s%s' %(chr(218-vol),chr(34+vol)),ser)
        if (command  == "POWER_Z1"):
            if (msg.payload.upper() == "ON"):
                sendAVR(CmdMsg["ON_Z1"],ser)
                time.sleep(1)
            if (msg.payload.upper() == "OFF"):
                sendAVR(CmdMsg["OFF_Z1"],ser)
            else:
                print("unknown command: %s" %command)
        time.sleep(0.06)

    lockser=0

def on_log(client, userdata, level, buf):
    print("log: ",buf)

client = paho.Client("AVR")
client.on_connect = on_connect
client.on_message = on_message
client.username_pw_set("AVR", "<password>")
client.connect("127.0.0.1", 1883, 60)
lockser = 0

run = True
while run:
    client.loop()
    if lockser == 0:
        readAVR(ser)
