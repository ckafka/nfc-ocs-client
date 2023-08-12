"""
nfc ocs server
"""

import nfc
import nfc.clf.device
import nfc.clf.transport

import errno
import signal
import time
import ndef

class Sighandler:
    def __init__(self) -> None:
        self.sigint = False
    
    def signal_handler(self, sig, han):
        self.sigint = True
        print(f'\n***{signal.Signals(sig).name} received. Exiting...***')

class NfcReader:
    """
    NFC reader 
    """
    def __init__(self, clf):
        self.clf = clf
        self.last_tag = None
        self.current_tag = None
        self.one_shot_affirmatives = ['yes', 'y', 'true']

    def update(self, tag):
        self.last_tag = self.current_tag
        self.current_tag = tag

        if tag.ndef is not None:
            for record in tag.ndef.records:
                if isinstance(record, ndef.TextRecord):
                    packet = record.text.split(";")
                    pattern = packet[0].split(":")[1]
                    one_shot = packet[1].split(":")[1] in self.one_shot_affirmatives
                    one_shot_transition = True
                    if self.last_tag is not None:
                        one_shot_transition = self.current_tag.identifier != self.last_tag.identifier

                    if not one_shot or (one_shot and one_shot_transition):
                        print(f'transmitting pattern={pattern}')


class NfcController:
    """
    NFC Controller -- supports polling multiple readers
    """
    def __init__(self) -> None:
        self.readers = []
        self.active_reader = None
        
        self.rw_params = {
            'on-startup' : self.start_poll,
            'on-connect' : self.tag_detected,
            'iterations' : 1,
            'interval' : 0.05
        }

        self.start_time_ms = time.time_ns() / 1000
        self.TIMEOUT_ms = 100

    def tag_detected(self, tag):
        """Print detected tag's NDEF data"""
        if tag.ndef is not None:
            self.active_reader.update(tag)
        else:
            print("Detected tag without NDEF record. Add a record and try again")

        return True

    def start_poll(self, targets):
        """Start the stop watch. Must return targets to clf"""
        self.start_time_ms = time.time_ns() / 1000
        return targets

    def timeout(self):
        """
        Return whether time > TIMEOUT_S has elapsed since last call of start_poll()
        """
        return (time.time_ns() / 1000) - self.start_time_ms > self.TIMEOUT_ms

    def close_all(self): 
        """
        Close all detected NFC readers. If reader is not closed correctly, it 
        will not initialize correctly on the next run due issue on PN532
        """
        for nfc_reader in self.readers:
            nfc_reader.clf.close()
        print("***Closed all readers***")

    def discover_readers(self):
        """Discover readers connected via FTDI USB to serial cables"""
        print("***Discovering Readers***")
        for dev in nfc.clf.transport.TTY.find("tty")[0]:
            path = "tty:{0}".format(dev[8:])
            try:
                clf = nfc.ContactlessFrontend(path)
                print(f'Found device: {clf.device}')
                self.readers.append(NfcReader(clf)) 
            except IOError as error:
                if error.errno == errno.ENODEV:
                    print(f'Reader found on {path} but not responding. Power cycle the reader and try again')
                else:
                    print(f'Unkown error: {error}')
    
    def poll_readers(self): 
        """Poll each reader for a card, print the tag"""
        print("***Polling***")
        for nfc_reader in self.readers:
            self.active_reader = nfc_reader
            try: 
                print(f'Polling reader {nfc_reader.clf.device}')
                tag = nfc_reader.clf.connect(rdwr=self.rw_params, terminate=self.timeout)
                if tag is None:
                    nfc_reader.update(None)
            except: 
                pass

if __name__ == "__main__":
    print("***CTRL+C or pskill python to exit***")
    controller = NfcController()
    controller.discover_readers()

    if len(controller.readers) == 0:
        print("***No devices found. Exiting***")
        exit() 

    handler = Sighandler()
    signal.signal(signal.SIGINT, handler.signal_handler)    
    signal.signal(signal.SIGTERM, handler.signal_handler)    
    while not handler.sigint:
        try: 
            controller.poll_readers()
            time.sleep(0.2)
        except:
            controller.close_all()
    controller.close_all()