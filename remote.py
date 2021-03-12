#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import serial.threaded

import pyftdi.serialext

import matplotlib
import matplotlib.pyplot as plt

import tkinter

import sys
import time
import csv

from threading import Thread
import logging

matplotlib.use('TkAgg')

logger = logging.getLogger('T962A_remote')
logger.setLevel(logging.DEBUG)



import profiling




# settings
#
FIELD_NAMES = 'Phase,Time,Temp0,Temp1,Temp2,Temp3,ColdJ,Set,Actual,Heat,Fan'
BAUD_RATE = 115200

def get_tty():
	return pyftdi.serialext.serial_for_url('ftdi://ftdi:232r/1', baudrate=BAUD_RATE)

class T962Connection(serial.threaded.LineReader):
	def __init__(self, consumer):
		super(serial.threaded.LineReader, self).__init__()
		self.consumer = consumer

	def synchronize(self):
		self.write_line('')
		time.sleep(0.1)

	def send_command(self, cmd):
		self.write_line(cmd)
		time.sleep(0.1)

	def get_info(self):
		self.send_command("info")

	def select_profile(self, index):
		self.send_command(f"set profile {index}")

	def dump_profile(self, index):
		self.send_command(f"dump profile {index}")

	def save_profile(self, setpoints):
		if len(setpoints) > 48:
			error("Too many setpoints")
		setpoints_string = ','.join([str(int(x)) for x in setpoints])
		self.send_command(f"save '' {setpoints_string}")

	def start_bake(self, setpoint, duration=None):
		if duration is not None:
			self.send_command(f"bake {setpoint} {duration}")
		else:
			self.send_command(f"bake {setpoint}")

	def start_reflow(self):
		self.send_command("set reflow_log_lvl 1")
		self.send_command("reflow")

	def abort_operation(self):
		self.send_command("abort")

	def set_minimum_fan_speed(self, value):
		self.send_command(f"set reflow_min_fan_speed {value}")

	def connection_made(self, transport):
		super(T962Connection, self).connection_made(transport)
		logger.debug('Connected to device\n')

	def connection_lost(self, exc):
		if exc:
			logger.error(exc, exc_info=True)
		logger.debug('Disconnected from device\n')

	def handle_line(self, line):
		# print(line)

		try:
			# ignore 'comments'
			if line.startswith('#'):
				return

			if line.startswith('[REFLOW]'):
				string = line[9:].strip()
				self.handle_reflow_log(string)
				return
		except:
			if len(line.strip()) > 0:
				print('!!', line)

	def handle_reflow_log(self, string):
		if string.startswith('START'):
			try:
				self.consumer.reflow_did_start()
			except Exception as e:
				logger.error(e, exc_info=True)
			return

		if string.startswith('END'):
			try:
				self.consumer.reflow_did_end()
			except Exception as e:
				logger.error(e, exc_info=True)
			return

		if string.startswith('BEGIN'):
			try:
				phase = string[6:].strip()
				self.consumer.reflow_did_begin_phase(phase)
			except Exception as e:
				logger.error(e, exc_info=True)
			return

		if string.startswith('LOG'):
			try:
				status_string = string[4:].strip()
				print(status_string)

				status = self.parse_status(status_string)
				self.consumer.reflow_did_emit_status(status)
			except Exception as e:
				logger.error(e, exc_info=True)
			return		

	def parse_status(self, status_string):
		values = list(map(str.strip, status_string.split()))
		# Convert all values to float, except the mode
		values = [values[0], ] + list(map(float, values[1:]))
		fields = FIELD_NAMES.split(',')
		if len(values) != len(fields):
			raise ValueError('Expected %d fields, found %d' % (len(fields), len(values)))
		return dict(zip(fields, values))

class TemperatureProfile:
	def __init__(self):
		self.points = []

	def add_point(self, t, temperature):
		self.points.append((t, temperature))

	def interpolate(self, t):
		index = self.find_index(t)
		length = len(self.points)

		if index == 0:
			return self.points[0][1]
		elif index == length:
			return self.points[length - 1][1]
		else:
			t0, temp0 = self.points[index - 1]
			t1, temp1 = self.points[index]

			f = (t - t0) / (t1 - t0)
			return f * (temp1 - temp0) + temp0

	def find_index(self, t):
		index = 0
		while index < len(self.points):
			if t < self.points[index][0]:
				return index
			index += 1
		return index

class ReflowData:
	def __init__(self, profile):
		self.profile = profile
		self.statuses = []

	def append_status(self, status):
		self.statuses.append(status)

	def values_for_key(self, key):
		return [s[key] for s in self.statuses]

	def time_values(self):
		return self.values_for_key('Time')

	def temp0_values(self):
		return self.values_for_key('Temp0')

	def temp1_values(self):
		return self.values_for_key('Temp1')

	def temp2_values(self):
		return self.values_for_key('Temp2')

	def temp3_values(self):
		return self.values_for_key('Temp3')

	def setpoint_values(self):
		return self.values_for_key('Set')

	def average_values(self):
		return self.values_for_key('Actual')

	def cold_junction_values(self):
		return self.values_for_key('ColdJ')

	def heat_values(self):
		return list(map(lambda x: x * (100.0 / 256.0), self.values_for_key('Heat')))

	def fan_values(self):
		return list(map(lambda x: x * (100.0 / 256.0), self.values_for_key('Fan')))

class EventConsumer:
	def __init__(self):
		self.reflow_data = ReflowData('Unknown')

	def reflow_did_start(self):
		self.reflow_data = ReflowData('Unknown')
		return

	def reflow_did_end(self):
		return

	def reflow_did_begin_phase(self, phase):
		if phase != 'COOLING':
			self.reflow_data = ReflowData('Unknown')
		return

	def reflow_did_emit_status(self, status):
		if self.reflow_data == None:
			self.reflow_data = ReflowData('Unknown')
		self.reflow_data.append_status(status)


class ReflowView:
	def __init__(self, profile):
		self.profile = profile

		self.time_limits = [0, 800]
		self.temp_limits = [0, 275]
		self.pwm_limits = [-5, 105]

		self.fig = plt.figure(figsize=(15, 12))
		self.fig.canvas.set_window_title('Reflow Profile')

		self.temp_top_axes = self.fig.add_subplot(7, 1, (1, 2))
		self.temp_pcb_axes = self.fig.add_subplot(7, 1, (3, 4))
		self.temp_pid_axes = self.fig.add_subplot(7, 1, (5, 6))
		self.pwm_axes = self.fig.add_subplot(7, 1, 7)

		# Temperature Sensors (Top)

		self.temp_top_pf_plot, = self.temp_top_axes.plot([], [], label='Profile', 		linewidth=1, color='#ff9944', zorder=3)
		self.temp_top_sp_plot, = self.temp_top_axes.plot([], [], label='Set Point', 	linewidth=1, color='#444444', zorder=1)
		self.temp_top_t0_plot, = self.temp_top_axes.plot([], [], label='Air Sensor A', 	linewidth=1, color='#008000', zorder=2)
		self.temp_top_t1_plot, = self.temp_top_axes.plot([], [], label='Air Sensor B', 	linewidth=1, color='#0000d0', zorder=2)

		self.temp_top_axes.grid(True, color='#dddddd')
		self.temp_top_axes.set_xticklabels([])
		self.temp_top_axes.set_ylabel('Temperature [°C]')
		self.temp_top_axes.legend(loc='upper left')

		# Temperature Sensors (Aux)

		self.temp_pcb_sp_plot, = self.temp_pcb_axes.plot([], [], label='Set Point', 	linewidth=2, color='#000000', zorder=1)
		self.temp_pcb_t2_plot, = self.temp_pcb_axes.plot([], [], label='PCB Sensor A', 	linewidth=1, color='#008000', zorder=2)
		self.temp_pcb_t3_plot, = self.temp_pcb_axes.plot([], [], label='PCB Sensor B', 	linewidth=1, color='#0000d0', zorder=2)

		self.temp_pcb_axes.grid(True, color='#dddddd')
		self.temp_pcb_axes.set_xticklabels([])
		self.temp_pcb_axes.set_ylabel('Temperature [°C]')
		self.temp_pcb_axes.legend(loc='upper left')

		# Temperature PID Inputs

		self.temp_pid_sp_plot, = self.temp_pid_axes.plot([], [], label='Set Point', linewidth=2, color='#000000', zorder=1)
		self.temp_pid_in_plot, = self.temp_pid_axes.plot([], [], label='PID Input', linewidth=1, color='#800000', zorder=2)
		
		self.temp_pid_axes.grid(True, color='#dddddd')
		self.temp_pid_axes.set_xticklabels([])
		self.temp_pid_axes.set_ylabel('Temperature [°C]')		
		self.temp_pid_axes.legend(loc='upper left')

		# PWM Outputs

		self.heater_plot, = self.pwm_axes.plot([], [], label='Heater', 	linewidth=1, color='#ee9900')
		self.fan_plot, 	  = self.pwm_axes.plot([], [], label='Fan', linewidth=1, color='#4444ff')
		
		self.pwm_axes.grid(True, color='#dddddd')
		self.pwm_axes.set_ylabel('Duty Cycle [%]')
		self.pwm_axes.set_xlabel('Time [seconds]')		
		self.pwm_axes.legend(loc='upper left')

		self.fig.canvas.toolbar.pack_forget()
		self.fig.tight_layout()

	def update(self, reflow_data):
		# Profile data

		ptimes, ptemps = self.profile.sample()

		# Retrieve data points

		time_values = reflow_data.time_values()
		temp0_values = reflow_data.temp0_values()
		temp1_values = reflow_data.temp1_values()
		temp2_values = reflow_data.temp2_values()
		temp3_values = reflow_data.temp3_values()

		setpoint_values = reflow_data.setpoint_values()
		average_values = reflow_data.average_values()

		heater_values = reflow_data.heat_values()
		fan_values = reflow_data.fan_values()

		# Update axes limits

		self._update_limits_from_values(self.time_limits, time_values,
														  ptimes)


		# self._update_limits_from_values(self.temp_limits, temp0_values,
		# 												  temp1_values,
		# 												  temp2_values,
		# 												  temp3_values,
		# 												  setpoint_values,
		#  												  average_values,
		#  												  ptemps)

		# self._update_limits_from_values(self.pwm_limits,  heater_values,
		# 												  fan_values)

		self._set_axes_limits()

		self.temp_top_pf_plot.set_data(ptimes, ptemps)
		self.temp_top_sp_plot.set_data(time_values, setpoint_values)
		self.temp_top_t0_plot.set_data(time_values, temp0_values)
		self.temp_top_t1_plot.set_data(time_values, temp1_values)

		# self.temp_pcb_sp_plot.set_data(ptimes, ptemps)
		self.temp_pcb_t2_plot.set_data(time_values, temp2_values)
		self.temp_pcb_t3_plot.set_data(time_values, temp3_values)
		
		
		self.temp_pid_in_plot.set_data(time_values, average_values)
		self.temp_pid_sp_plot.set_data(time_values, setpoint_values)

		self.heater_plot.set_data(time_values, heater_values)
		self.fan_plot.set_data(time_values, fan_values)

		plt.draw()

	def run_event_loop(self, interval):
		# The following code replaces the common pyplot idoim `pause()`.
		# Although the use of `pause(...)` is the standard technique for
		# writing non-blocking pyplot graphics, each time it's invoked,
		# it steals focus from the currently active window and moves
		# itself to the top of the window stack. It isn't ideal... 
		# 
		# Replacing an officially maintained solution with a hack, such
		# as the one below, has serious drawbacks. However, for now, it
		# works with the current versions and the alternative is janky.  
		backend = plt.rcParams['backend']
		if backend in matplotlib.rcsetup.interactive_bk:
			figManager = matplotlib._pylab_helpers.Gcf.get_active()
			if figManager is not None:
				canvas = figManager.canvas
				if canvas.figure.stale:
					canvas.draw()
				canvas.start_event_loop(interval)
				return		

	def _update_limits_from_values(self, limits, *values_list):
		for values in values_list:
			if len(values) == 0:
				continue

			min_value = min(values)
			max_value = max(values)

			if limits[0] > min_value:
				limits[0] = min_value
			if limits[1] < max_value:
				limits[1] = max_value

	def _set_axes_limits(self):
		self.temp_top_axes.set_xlim(*self.time_limits)
		self.temp_top_axes.set_ylim(*self.temp_limits)

		self.temp_pcb_axes.set_xlim(*self.time_limits)
		self.temp_pcb_axes.set_ylim(*self.temp_limits)

		self.temp_pid_axes.set_xlim(*self.time_limits)
		self.temp_pid_axes.set_ylim(*self.temp_limits)

		self.pwm_axes.set_xlim(*self.time_limits)
		self.pwm_axes.set_ylim(*self.pwm_limits)


def main():

	pb = profiling.Builder_Tweak()

	profile = pb.build()
	_, profile_samples = profile.sample(10, False)

	print(f"Total samples in reflow profile: {len(profile_samples)}")

	consumer = EventConsumer()
	reflow_view = ReflowView(profile)

	plt.ion();
	plt.show()

	port = get_tty()

	def build_connection():
		return T962Connection(consumer)

	try:
		with serial.threaded.ReaderThread(port, build_connection) as conn:
			try:
				conn.synchronize()

				conn.set_minimum_fan_speed(16)

				conn.select_profile(4)
				conn.save_profile(profile_samples)

				conn.select_profile(4)
				conn.start_reflow()

				while True:
					if consumer.reflow_data != None:
						reflow_view.update(consumer.reflow_data)
					reflow_view.run_event_loop(1)
			finally:
				conn.abort_operation()
	except KeyboardInterrupt:
		pass 

if __name__ == '__main__':
	main()
