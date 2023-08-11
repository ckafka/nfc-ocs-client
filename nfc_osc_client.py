"""
nfc ocs server
"""

import nfc
import nfc.clf.device
import nfc.clf.transport

import errno


def discover_readers():
    """Discover devices"""
    clfs = []
    for dev in nfc.clf.transport.TTY.find("tty")[0]:
        path = "tty:{0}".format(dev[8:])
        try:
            clf = nfc.ContactlessFrontend(path)
            clfs.append(clf) 
            print("found %s" % clf.device)
        except IOError as error:
            if error.errno == errno.EACCES:
                print("access denied")
            elif error.errno == errno.EBUSY:
                print("busy")


if __name__ == "__main__":
    discover_readers()
