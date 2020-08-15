
# This example shows using two TSL2491 light sensors attached to TCA9548A channels 0 and 1.
# Use with other I2C sensors would be similar.
import time
import board
import busio
import adafruit_tsl2561
import adafruit_tca9548a

from numpy import mean

CLOSER_SENSOR = 7
FURTHER_SENSOR = 2

# Create I2C bus as normal
i2c = busio.I2C(board.SCL, board.SDA)

# Create the TCA9548A object and give it the I2C bus
tca = adafruit_tca9548a.TCA9548A(i2c)

# For each sensor, create it using the TCA9548A channel instead of the I2C object
outer_tsl = adafruit_tsl2561.TSL2561(tca[FURTHER_SENSOR])
inner_tsl = adafruit_tsl2561.TSL2561(tca[CLOSER_SENSOR])

# Loop and profit!
try:
    while True:
        outer, inner = outer_tsl.infrared, inner_tsl.infrared
        avg = int(mean((outer, inner)))
        diff = outer - inner
        diff_percent = int(diff/avg * 100) if avg else 0
        print("outer sensor:\t", outer)
        print("inner sensor:\t", inner)
        print("average     :\t", avg)
        print("diff        :\t", diff)
        print("diff percent:\t {}%".format(diff_percent))
        print()
        time.sleep(.5)
except KeyboardInterrupt:
    print("Stopped")
