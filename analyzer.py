#!/usr/bin/env python
import matplotlib
import matplotlib.pyplot as plt

def load_data(file_name):
	file = open(file_name, 'r') 
	lines = file.readlines()

	FIELD_NAMES = 'Mode,Time,Temp0,Temp1,Temp2,Temp3,ColdJ,Set,Actual,Heat,Fan'

	def parse_line(line):
		values = list(map(str.strip, line.split()))
		# Convert all values to float, except the mode
		values = [values[0], ] + list(map(float, values[1:]))
		fields = FIELD_NAMES.split(',')
		if len(values) != len(fields):
			raise ValueError('Expected %d fields, found %d' % (len(fields), len(values)))
		return dict(zip(fields, values))

	all_data = map(parse_line, lines)
	reflow_data = list(filter(lambda x: x['Mode'] == 'PROFILE', all_data))

	times = [x['Time'] for x in reflow_data]
	temps = [x['Temp3'] for x in reflow_data]

	return times, temps

def time_to(ts, values, threshold):
	for i, t in enumerate(ts):
		value = values[i]
		if value > threshold:
			return t
	return None

def time_above(ts, values, threshold):
	total_time = 0
	is_above = False
	t_start = 0

	for i, t in enumerate(ts):
		value = values[i]

		if not is_above and value >= threshold:
			is_above = True
			t_start = t
		
		if is_above and value < threshold:
			is_above = False
			total_time += t - t_start

	if is_above:
		total_time += ts[-1] - t_start

	return total_time

def peak_onset(ts, values):
	peak = max(values)
	for i, t in enumerate(ts):
		value = values[i]
		if value == peak:
			return t, peak
	return None, None





ts, temps = load_data('multiphase_example1.txt')




peak_time, peak_temp = peak_onset(ts, temps)
time_above_soak = time_above(ts, temps, 200)
time_above_liquidus = time_above(ts, temps, 217)

time_to_soak_min = time_to(ts, temps, 150)
time_to_soak_max = time_to(ts, temps, 200)
time_of_soak = time_to_soak_max - time_to_soak_min

print(f"Peak temperature: {peak_temp:.2f}C")

print(f"Time of peak: {peak_time:.2f}s")
print(f"Time above soak: {time_above_soak:.2f}s")
print(f"Time above liquidus: {time_above_liquidus:.2f}s")
print(f"Time of soak: {time_of_soak:.2f}")


fig, ax = plt.subplots()
ax.plot(ts, temps)
plt.show()



