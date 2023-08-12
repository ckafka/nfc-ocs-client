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


class TagCommand: 
    def __init__(self, record):
        try: 
            self.tag_data = record.text.split(";")
            self.valid_header = self.tag_data[0] == "eldermother"
            self.pattern = self.tag_data[1].split(":")[1]
            self.one_shot = self.tag_data[2].split(":")[1] in ['yes', 'y', 'true']
        except Exception as e: 
            print(f'{e}')


class CustomTextTag:
    def __init__(self, tag): 
        self.tag = tag
        self.cmd = None
        if tag.ndef is not None:
            record = tag.ndef.records[0]
            if isinstance(record, ndef.TextRecord):
                self.cmd = TagCommand(record)
        
    def is_header_valid(self): 
        if self.cmd is None:
            return False 
        else:
            return self.cmd.valid_header

    def get_pattern(self):
        if self.cmd is None: 
            return ""
        return self.cmd.pattern

    def is_one_shot(self): 
        if self.cmd is None:
            return False
        return self.cmd.one_shot

class NfcReader:
    """
    NFC reader 
    """
    def __init__(self, clf):
        self.clf = clf
        self.last_tag = None
        self.current_tag = None

    def update(self, tag):
        self.last_tag = self.current_tag
        self.current_tag = tag

        text_tag = CustomTextTag(tag)
        if text_tag.is_header_valid():
            one_shot_transition = True
            if self.last_tag is not None:
                one_shot_transition = self.current_tag.identifier != self.last_tag.identifier

            if not text_tag.is_one_shot() or (text_tag.is_one_shot() and one_shot_transition):
                print(f'transmitting pattern={text_tag.get_pattern()}, one-shot={text_tag.is_one_shot()}')
        else:
            print("Missing NFC NDEF header text. Format and try again")

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
            'interval' : 0.5
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
        self.start_time_ms = time.time_ns() / 1000000
        return targets

    def timeout(self):
        """
        Return whether time > TIMEOUT_S has elapsed since last call of start_poll()
        """
        elapsed = (time.time_ns() / 1000000) - self.start_time_ms
        return elapsed > self.TIMEOUT_ms

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