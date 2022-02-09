from time import sleep
import logging as log
import io
import pyqtgraph as pg
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QThread
import numpy as np
from PIL import Image
from ..Quadro import Quadro


class DectrisImageGrabber(QObject):
    image_ready = pyqtSignal(np.ndarray)
    exposure_triggered = pyqtSignal()
    connected = False

    def __init__(self, ip, port, trigger_mode='ints', exposure=0.3):
        super().__init__()

        self.Q = Quadro(ip, port)
        try:
            _ = self.Q.state
            self.connected = True
            log.info(f'DectrisImageGrabber successfully connected to detector\n{self.Q}')
        except OSError:
            log.warning('DectrisImageGrabber could not establish connection to detector')

        if self.connected:
            if self.Q.state == 'na':
                log.warning('Detector needs to be initialized, that may take a while...')
                self.Q.initialize()
            self.Q.mon.clear()
            self.Q.fw.clear()
            self.Q.fw.mode = 'disabled'
            self.Q.mon.mode = 'enabled'
            self.Q.incident_energy = 1e5
            self.Q.count_time = exposure
            self.Q.frame_time = exposure
            self.Q.trigger_mode = trigger_mode

        self.image_grabber_thread = QThread()
        self.moveToThread(self.image_grabber_thread)
        self.image_grabber_thread.started.connect(self.__get_image)

    def __del__(self):
        if self.connected:
            self.Q.mon.clear()
            self.Q.disarm()

    @pyqtSlot()
    def __get_image(self):

        log.debug(f'started image_grabber_thread {self.image_grabber_thread.currentThread()}')

        if self.connected:
            self.Q.arm()
            if self.Q.trigger_mode == 'ints':
                self.exposure_triggered.emit()
                self.wait_for_state('idle')
                self.Q.trigger()
                self.wait_for_state('idle', False)
                self.Q.disarm()
            if self.Q.trigger_mode == 'exts':
                self.wait_for_state('ready')
                self.exposure_triggered.emit()
                self.wait_for_state('acquire')
            while not self.Q.mon.image_list:
                if self.image_grabber_thread.isInterruptionRequested():
                    self.image_grabber_thread.quit()
                    return
                sleep(0.05)
            # image comes as a file-like object in tif format
            self.image_ready.emit(np.array(Image.open(io.BytesIO(self.Q.mon.last_image))))
            self.Q.mon.clear()
        else:
            self.exposure_triggered.emit()
            sleep(1)
            x = np.linspace(-10, 10, 512)
            xs, ys = np.meshgrid(x, x)
            img = 5e4 * ((np.cos(np.hypot(xs, ys)) / (np.hypot(xs, ys)+1) * np.random.normal(1, 0.1, (512, 512))) + 0.3)
            self.image_ready.emit(img)

        self.image_grabber_thread.quit()
        log.debug(f'quit image_grabber_thread {self.image_grabber_thread.currentThread()}')

    def wait_for_state(self, state_name, logic=True):
        log.debug(f'waiting for state: {state_name} to be {logic}')
        if logic:
            while self.Q.state == state_name:
                if self.image_grabber_thread.isInterruptionRequested():
                    self.image_grabber_thread.quit()
                    return
                sleep(0.05)
            return
        while self.Q.state != state_name:
            if self.image_grabber_thread.isInterruptionRequested():
                self.image_grabber_thread.quit()
                return
            sleep(0.05)




class DectrisStatusGrabber(QObject):
    status_ready = pyqtSignal(dict)
    connected = False

    def __init__(self, ip, port):
        super().__init__()

        self.Q = Quadro(ip, port)
        try:
            _ = self.Q.state
            self.connected = True
            log.info('DectrisStatusGrabber successfully connected to detector')
        except OSError:
            log.warning('DectrisStatusGrabber could not establish connection to detector')

        self.status_grabber_thread = QThread()
        self.moveToThread(self.status_grabber_thread)
        self.status_grabber_thread.started.connect(self.__get_status)

    @pyqtSlot()
    def __get_status(self):
        log.debug(f'started status_grabber_thread {self.status_grabber_thread.currentThread()}')
        if self.connected:
            self.status_ready.emit({'quadro': self.Q.state, 'fw': self.Q.fw.state, 'mon': self.Q.mon.state,
                                    'trigger_mode': self.Q.trigger_mode, 'exposure': self.Q.frame_time})
        else:
            self.status_ready.emit({'quadro': None, 'fw': None, 'mon': None, 'trigger_mode': None, 'exposure': None})
        self.status_grabber_thread.quit()
        log.debug(f'quit status_grabber_thread {self.status_grabber_thread.currentThread()}')


class ExposureProgressWorker(QObject):
    advance_progress_bar = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.progress_thread = QThread()
        self.moveToThread(self.progress_thread)
        self.progress_thread.started.connect(self.__start_progress)

    @pyqtSlot()
    def __start_progress(self):
        while True:
            if self.progress_thread.isInterruptionRequested():
                self.progress_thread.quit()
                return
            self.advance_progress_bar.emit()
            sleep(0.01)


def interrupt_liveview(f):
    def wrapper(self):
        log.debug('stopping liveview')
        self.image_timer.stop()
        if self.dectris_image_grabber.connected:
            if not self.dectris_image_grabber.image_grabber_thread.isFinished():
                log.debug('aborting acquisition')
                self.dectris_image_grabber.Q.abort()
                self.dectris_image_grabber.image_grabber_thread.requestInterruption()
                self.dectris_image_grabber.image_grabber_thread.wait()
        f(self)
        log.debug('restarting liveview')
        self.image_timer.start(self.update_interval)
    return wrapper
