"""
nfc ocs server
"""

import nfc
import nfc.clf.device
import nfc.clf.transport

import errno

class NfcController:
    def __init__(self) -> None:
        self.clfs = []

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
        for nfc_reader in self.clfs:
            tag = nfc_reader.connect(rdwr={})
            print("device %s " % nfc_reader.device)
            print("found tag %s" % tag)

if __name__ == "__main__":
    controller = NfcController()
    while True: 
        controller.discover_readers()
