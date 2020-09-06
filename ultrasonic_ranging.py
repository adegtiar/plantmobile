#!/usr/bin/env python3
########################################################################
# Filename    : UltrasonicRanging.py
# Description : Get distance via UltrasonicRanging sensor
# auther      : www.freenove.com
# modification: 2019/12/28
########################################################################
import RPi.GPIO as GPIO
import time

import adafruit_hcsr04
import board

MAX_DISTANCE = 100          # define the maximum measuring distance, unit: cm
timeOut = MAX_DISTANCE*60   # calculate timeout according to the maximum measuring distance


#class DistanceSensor(object):
#
#    def __init__(self, trig_pin, echo_pin, max_distance=MAX_DISTANCE):
#        self.trig_pin = trig_pin
#        self.echo_pin = echo_pin
#        self.timeout = max_distance*60

def pulseIn(pin,level,timeOut): # obtain pulse time of a pin under timeOut
    t0 = time.time()
    while(GPIO.input(pin) != level):
        if((time.time() - t0) > timeOut*0.000001):
            return 0;
    t0 = time.time()
    while(GPIO.input(pin) == level):
        if((time.time() - t0) > timeOut*0.000001):
            return 0;
    pulseTime = (time.time() - t0)*1000000
    return pulseTime
    
def getSonar():     # get the measurement results of ultrasonic module,with unit: cm
    GPIO.output(trigPin,GPIO.HIGH)      # make trigPin output 10us HIGH level 
    time.sleep(0.00001)     # 10us
    GPIO.output(trigPin,GPIO.LOW) # make trigPin output LOW level 
    pingTime = pulseIn(echoPin,GPIO.HIGH,timeOut)   # read plus time of echoPin
    distance = pingTime * 340.0 / 2.0 / 10000.0     # calculate distance with sound speed 340m/s 
    return distance
    
def setup():
    GPIO.setmode(GPIO.BCM)          # use BCM GPIO Numbering
    #GPIO.setup(trigPin, GPIO.OUT)   # set trigPin to OUTPUT mode
    #GPIO.setup(echoPin, GPIO.IN)    # set echoPin to INPUT mode

def loop():
    while(True):
        distance = getSonar() # get distance
        print ("The distance is : %.2f cm"%(distance))
        time.sleep(.1)

def loop_gpiozero(distance_sensor):
    sensor = DistanceSensor(echo=echoPin, trigger=trigPin, threshold_distance=0.1, partial=True, queue_len=1)
    while(True):
        distance = distance_sensor.distance * 100
        print ("The distance is : %.2f cm"%(distance))
        time.sleep(.1)

def loop_adafruit():
    sensor = adafruit_hcsr04.HCSR04(trigger_pin=board.D4, echo_pin=board.D17)
    while(True):
        try:
            distance = sensor.distance
            print ("The distance is : %.2f cm"%(distance))
        except RuntimeError:
            print ("time out waiting for response")
        time.sleep(.1)


trigPin = 4
echoPin = 17

if __name__ == '__main__':     # Program entrance
    print ('Program is starting...')
    setup()
    try:
        loop_adafruit()
    except KeyboardInterrupt:  # Press ctrl-c to end the program.
        #GPIO.cleanup()         # release GPIO resource
        pass


    
