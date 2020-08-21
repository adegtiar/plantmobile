#!/usr/bin/python3

# Script to read data from the CSV and display it in a graph:

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.animation as animation
import numpy as np

from matplotlib import style
from datetime import datetime

LAST_N_POINTS = 500

style.use('seaborn-whitegrid')
fig = plt.figure(num='Luminosity of Outer & Inner Sensors', figsize=[13,3])
ax1 = fig.add_subplot(1,1,1)
def animate(i):
    ftemp = 'data/sensor_log.csv'
    fh = open(ftemp)
    outer_luxes = []
    inner_luxes = []
    avg_luxes = []
    timestamps = []
    for line in fh:
        isotime, outer_lux, inner_lux = line.split(',')
        timestamp = datetime.fromisoformat(isotime)
        outer_luxes.append(float(outer_lux))
        inner_luxes.append(float(inner_lux))
        avg_luxes.append((float(inner_lux) + float(outer_lux)) / 2)
        timestamps.append(timestamp)

    if LAST_N_POINTS:
        outer_luxes = outer_luxes[-LAST_N_POINTS:]
        inner_luxes = inner_luxes[-LAST_N_POINTS:]
        avg_luxes = avg_luxes[-LAST_N_POINTS:]
        timestamps = timestamps[-LAST_N_POINTS:]

    ax1.clear()
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax1.plot_date(timestamps, outer_luxes, '-')
    ax1.plot_date(timestamps, inner_luxes, '-')
    ax1.plot_date(timestamps, avg_luxes, '-')
    ax1.legend(['Outer Luminosity', 'Inner Luminosity'])
    plt.xlabel('Time')
    plt.ylabel('Lux')

ani = animation.FuncAnimation(fig, animate, interval = 6000)
plt.show()

# outer: 3872, inner: 8388
#outer sensor:    3497
#inner sensor:    5805
