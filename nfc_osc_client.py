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

from pythonosc.udp_client import SimpleUDPClient

ip = "127.0.0.1"
port = 7777

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
            try:
                record = tag.ndef.records[0]
                if isinstance(record, ndef.TextRecord):
                    self.cmd = TagCommand(record)
            except Exception as e:
                print(f'{e}')
        
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

        self.active_custom_tag = None
        self.active = False
        self.one_shot_enabled = False

    def update(self, tag): 
        self.last_tag = self.current_tag
        self.current_tag = tag

    def is_new_tag_available(self, tag):
        if tag is not None: 
            print("Checking if tag is valid....")
            new_text_tag = CustomTextTag(tag)
            if new_text_tag.is_header_valid():
                print("Valid header")
                if self.active: 
                    print(f'Detected already active tag')
                    return False

                self.active_custom_tag = new_text_tag
                return True
            else:
                print("Missing NFC NDEF header text. Format and try again")

        return False 

    def set_pattern_as_active(self):
        self.active = True

    def deactivate(self):
        print("Tag Removed")
        self.active = False
        self.one_shot_enabled = False
        self.active_custom_tag = None

class NfcController:
    """
    NFC Controller -- supports polling multiple readers
    """
    def __init__(self) -> None:
        self.readers = []
        self.reader_index = 0

        self.client = SimpleUDPClient(ip, port)
        
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
        print("Tag detected")
        if tag.ndef is not None:
            try: 
                current_reader = self.readers[self.reader_index]
                if current_reader.is_new_tag_available(tag):
                    print(f'Valid new tag detected')
                    custom_tag = current_reader.active_custom_tag
                    address = f'/channel/{self.reader_index}/pattern/{custom_tag.get_pattern()}/enable'
                    data = 'T'
                    print(f'Activating pattern: {address}/{data}, one-shot: {custom_tag.is_one_shot()}')
                    self.client.send_message(address, data)
                    current_reader.set_pattern_as_active()
                    current_reader.one_shot_enabled = True

            except Exception as e:
                print(f'{e}')
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
        for dev in nfc.clf.transport.TTY.find("ttyUSB")[0]:
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

        self.reader_index = 0
        for nfc_reader in self.readers:
            try: 

                print(f'Polling reader {nfc_reader.clf.device}')
                if nfc_reader.active:
                    custom_tag = nfc_reader.active_custom_tag
                    if custom_tag.is_one_shot() and nfc_reader.one_shot_enabled:
                        address = f'/channel/{self.reader_index}/pattern/{custom_tag.get_pattern()}/enable'
                        data = "F"
                        print(f'Deactivating one-shot pattern: {address}/{data}, one-shot: {custom_tag.is_one_shot()}')
                        self.client.send_message(address, data)
                        nfc_reader.one_shot_enabled = False
                tag = nfc_reader.clf.connect(rdwr=self.rw_params, terminate=self.timeout)
                nfc_reader.update(tag)

                if tag is None:
                    if nfc_reader.active:
                        custom_tag = self.readers[self.reader_index].active_custom_tag
                        if not custom_tag.is_one_shot():
                            address = f'/channel/{self.reader_index}/pattern/{custom_tag.get_pattern()}/enable'
                            data = "F"
                            print(f'Deactivating pattern: {address}/{data}')
                            self.client.send_message(address, data)
                        nfc_reader.deactivate()
            except: 
                pass
            self.reader_index += 1
        

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


# if __name__ == "__main__":
#     client = SimpleUDPClient("127.0.0.1", 7777)
#     for x in range(10):
#         client.send_message("/filter", 5)
#         time.sleep(1)
#         print("hi")