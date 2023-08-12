"""
nfc ocs server
"""

import nfc
import nfc.clf.device
import nfc.clf.transport

import errno
import signal
import time

class Sighandler:
    def __init__(self) -> None:
        self.sigint = False
    
    def signal_handler(self, sig, han):
        self.sigint = True
        print(f'\n***{signal.Signals(sig).name} received. Exiting...***')


class NfcController:
    """
    NFC Controller class. Supports polling multiple readers
    """
    def __init__(self) -> None:
        self.clfs = []
        
        self.rw_params = {
            'on-startup' : self.start_poll,
            'on-connect' : self.print_tag,
            'iterations' : 2,
            'interval' : 0.1
        }

        self.start_time = time.time()
        self.TIMEOUT_S = 0.2

    def print_tag(self, tag):
        """Print detected tag's NDEF data"""
        try: 
            print(f'Detected tag with data: {tag.ndef.records}')
        except:
            print("Detected tag without NDEF record. Add a record and try again")
        return True

    def start_poll(self, targets):
        """Start the stop watch. Must return targets to clf"""
        self.start_time = time.time()
        return targets

    def timeout(self):
        """
        Return whether time > TIMEOUT_S has elapsed since last call of start_poll()
        """
        return time.time() - self.start_time > self.TIMEOUT_S

    def close_all(self): 
        """
        Close all detected NFC readers. If reader is not closed correctly, it 
        will not initialize correctly on the next run due issue on PN532
        """
        for nfc_reader in self.clfs:
            nfc_reader.close()
        print("***Closed all readers***")

    def discover_readers(self):
        """Discover readers connected via FTDI USB to serial cables"""
        print("***Discovering Readers***")
        for dev in nfc.clf.transport.TTY.find("tty")[0]:
            path = "tty:{0}".format(dev[8:])
            try:
                clf = nfc.ContactlessFrontend(path)
                self.clfs.append(clf) 
                print(f'Found device: {clf.device}')
            except IOError as error:
                if error.errno == errno.ENODEV:
                    print(f'Reader found on {path} but not responding. Power cycle the reader and try again')
                else:
                    print(f'Unkown error: {error}')
    
    def poll_readers(self): 
        """Poll each reader for a card, print the tag"""
        i = 0
        print("***Polling***")
        for nfc_reader in self.clfs:
            try: 
                nfc_reader.connect(rdwr=self.rw_params, terminate=self.timeout)
                print(f'Polled reader {nfc_reader.device}')
                i = i + 1
            except: 
                pass

if __name__ == "__main__":
    controller = NfcController()
    controller.discover_readers()

    if len(controller.clfs) == 0:
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