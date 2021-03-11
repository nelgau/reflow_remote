#!/usr/bin/env python
import sys

#from PyQt5.QtCore import QApplication

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

import pyqtgraph as pg

class ReflowRemote(QMainWindow):
	def __init__(self, parent=None):
		super(ReflowRemote, self).__init__(parent)

		self.setWindowTitle("Reflow Remote")

		self.create_main_frame()

		self.count = 0

		self.timer = QTimer()
		self.timer.timeout.connect(self.on_timer)

		self.timer.start(500)

	def create_main_frame(self):
		self.plot_widget = self.create_plot()
		self.serial_log = self.create_serial_log()

		main_layout = QVBoxLayout()
		main_layout.addWidget(self.plot_widget)
		main_layout.addWidget(self.serial_log)

		self.main_frame = QWidget()
		self.main_frame.setLayout(main_layout)

		self.setCentralWidget(self.main_frame)

		hour = [1,2,3,4,5,6,7,8,9,10]
		temperature_1 = [30,32,34,32,33,31,29,32,35,45]
		temperature_2 = [50,35,44,22,38,32,27,38,32,44]

		self.plot(hour, temperature_1, "Sensor1", 'r')
		self.plot(hour, temperature_2, "Sensor2", 'b')

	def create_plot(self):
		plot_widget = pg.PlotWidget()

		#Add Background colour to white
		plot_widget.setBackground('w')

		# Add Axis Labels
		styles = {"color": "#111", "font-size": "15px"}
		plot_widget.setLabel("left", "Temperature (°C)", **styles)
		plot_widget.setLabel("bottom", "Time (S)", **styles)

		#Add legend
		plot_widget.addLegend()

		#Add grid
		plot_widget.showGrid(x=True, y=True)

		#Set Range
		plot_widget.setXRange(0, 10, padding=0)
		plot_widget.setYRange(20, 55, padding=0)

		return plot_widget 

	def plot(self, x, y, plotname, color):
		pen = pg.mkPen(color=color)
		self.plot_widget.plot(x, y, name=plotname, pen=pen)

	def create_serial_log(self):
		serial_log = QTextEdit()
		serial_log.setReadOnly(True)
		serial_log.setLineWrapMode(QTextEdit.NoWrap)

		font = serial_log.font()
		font.setFamily("Courier")
		font.setPointSize(10)

		return serial_log

	def on_timer(self):
		self.count += 1
		self.serial_log.setPlainText(f"{self.count}")

def main():
	app = QApplication(sys.argv)
	app.setApplicationName("Reflow Remote")
	
	window = ReflowRemote()
	window.show()

	result = app.exec_()
	sys.exit(result)

if __name__ == '__main__':
	main()
