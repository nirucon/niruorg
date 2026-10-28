#!/usr/bin/env python3
import os
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QEventLoop, QThreadPool, QTimer
from PySide6.QtWidgets import QApplication
from niruorg.utils.workers import TaskWorker

app = QApplication([])
pool = QThreadPool()
loop = QEventLoop()
timer = QTimer()
ticks = 0
results = []
errors = []

def tick():
    global ticks
    ticks += 1

timer.timeout.connect(tick)
timer.start(15)
worker = TaskWorker(time.sleep, 0.20)
worker.signals.done.connect(lambda value: (results.append(value), loop.quit()))
worker.signals.failed.connect(lambda value: (errors.append(value), loop.quit()))
pool.start(worker)
QTimer.singleShot(3000, loop.quit)
loop.exec()
timer.stop()
pool.waitForDone(2000)
assert not errors, errors
assert results == [None], results
assert ticks >= 2, ticks
print('async task worker regression OK')
