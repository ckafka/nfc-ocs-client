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

class NfcController:
    def __init__(self) -> None:
        self.clfs = []
        
        self.rw_params = {
            'on-startup' : self.start_poll,
            'on-connect' : self.print_tag,
            'iterations' : 2,
            'interval' : 0.1
        }

        self.start_time = time.time()

    def print_tag(self, tag):
        try: 
            print("found tag with data: " + str(tag.ndef.records))   
        except:
            print("non NDEF tag found")
        return True

    def start_poll(self, targets):
        self.start_time = time.time()
        return targets

    def timeout(self):
        return time.time() - self.start_time > 0.5

    def close_all(self): 
        """close devices"""
        for nfc_reader in self.clfs:
            nfc_reader.close()
        print("closed readers")

    def discover_readers(self):
        """Discover readers connected via FTDI USB to serial cables"""
        for dev in nfc.clf.transport.TTY.find("tty")[0]:
            path = "tty:{0}".format(dev[8:])
            try:
                clf = nfc.ContactlessFrontend(path)
                self.clfs.append(clf) 
                print("found %s" % clf.device)
            except IOError as error:
                if error.errno == errno.EACCES:
                    print("access denied")
                elif error.errno == errno.EBUSY:
                    print("busy")
    
    def poll_readers(self): 
        """Poll each reader for a card, print the tag"""
        i = 0
        for nfc_reader in self.clfs:
            nfc_reader.connect(rdwr=self.rw_params, terminate=self.timeout)
            print("Polled reader no: " + str(i))
            i = i + 1

if __name__ == "__main__":
    controller = NfcController()
    controller.discover_readers()

    if len(controller.clfs) == 0:
        print("No devices found")
        exit() 

    handler = Sighandler()
    signal.signal(signal.SIGINT, handler.signal_handler)    
    while not handler.sigint:
        try: 
            controller.poll_readers()
        except:
            controller.close_all()

    controller.close_all()
