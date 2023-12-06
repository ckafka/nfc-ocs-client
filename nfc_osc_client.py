"""
nfc ocs server
"""
import errno
import signal
import time
import sys
import argparse
import json
import lgpio
import threading


import nfc
import nfc.clf.device
import nfc.clf.transport
from osc_tcp_client import OscTcpClient
from binascii import hexlify


from nfc_tags import CustomTextTag, HardCodedTag


class Sighandler:
    """SIGTERM and SIGINT handler"""

    def __init__(self) -> None:
        self.sigint = False

    def signal_handler(self, sig, han):
        """Ack received handler"""
        self.sigint = True
        print(f"\n***{signal.Signals(sig).name} received. Exiting...***")


class NfcReader:
    """
    NFC reader
    """
    global thread_call

    def __init__(self, clf, led_gpio, gpio_if, client, index):
        self.clf = clf
        self.last_tag = None
        self.current_tag = None

        self.active_tag = None
        self.activated = False

        config_file = open("configs/elder_mother_tags.json", "r")
        self.tag_dictionary = json.load(config_file)

        self.led_gpio = int(led_gpio)
        self.gpio_if = gpio_if
        lgpio.gpio_claim_output(gpio_if, self.led_gpio)
        self.set_led(True)
        self.led_enabled = True

        self.chromatik_client = client
        self.reader_index = index

        self.rw_params = {
            "on-connect": self.tag_detected,
            "on-release": self.tag_removed,
            "iterations": 5,
            "interval": 0.5,
        }

        self.init_thread()

    def thread_call(clf, params):
        while True:
            try: 
                clf.connect(rdwr=params)
            except: 
                print("stopped thread")  
                return

    def init_thread(self):
        new_thread = threading.Thread(target=thread_call, kwargs={"clf": self.clf, "params":self.rw_params})
        new_thread.start()

    def update(self, tag):
        """Set new tag information"""
        self.last_tag = self.current_tag
        self.current_tag = tag

    def set_led(self, state): 
        self.led_enabled = state
        # lgpio.gpio_write(self.gpio_if, self.led_gpio, self.led_enabled)
        if state:
            lgpio.tx_pwm(self.gpio_if, self.led_gpio, 1000, 50)
        else: 
            lgpio.tx_pwm(self.gpio_if, self.led_gpio, 1000, 0)

    def tag_detected(self, tag):
        """Print detected tag's NDEF data"""
        print("Tag detected")
        self.update(tag)
        if self.is_current_tag_new_and_valid():
            self.chromatik_client.tx_pattern_enable(
                self.reader_index,
                self.active_tag.get_pattern(),
                self.active_tag.is_one_shot(),
            )
            self.activated = True

        return True

    def tag_removed(self, tag):
        self.update(tag)
        if self.activated:
            if not self.active_tag.is_one_shot():
                self.chromatik_client.tx_pattern_disable(
                    self.reader_index, self.active_tag.get_pattern()
                )
            print("Tag Removed")
            self.activated = False
            self.set_led(True)
            self.active_tag = None

    def is_current_tag_new_and_valid(self):
        """Return true if the current tag is new and valid"""

        if self.activated:
            print("A tag is already active")
            self.set_led(not self.led_enabled)
            return False

        valid = False
        if self.current_tag is not None:
            print("Checking if tag is valid....")
            if self.current_tag.ndef is not None:
                print("Detected tag with NDEF record. Checking header...")
                new_text_tag = CustomTextTag(self.current_tag)
                if new_text_tag.is_header_valid():
                    print("Valid header")
                    self.active_tag = new_text_tag
                    valid = True
                else:
                    print("Missing NFC NDEF header text. Format and try again")
            else:
                print("Detected tag without NDEF record. Checking dictionary...")
                tag_id = hexlify(self.current_tag.identifier).decode().upper()
                if tag_id in self.tag_dictionary:
                    values = self.tag_dictionary[tag_id]
                    print(f"Found tag {tag_id} with params {values}")
                    self.active_tag = HardCodedTag(
                        self.current_tag, values[0], values[1], values[2]
                    )
                    valid = True
                else:
                    print("Unknown tag, please add to dictionary")
            return valid
    

class ChromatikOcsClient:
    """Osc Client for Chromatik"""

    def __init__(self, dest_ip, dest_port) -> None:
        try:
            self.dest_ip = dest_ip
            self.dest_port = dest_port
            self.client = OscTcpClient(dest_ip, dest_port)
            self.connected = self.client.connected
        except Exception as unkown_err:
            self.init = False
            print(f"Error: ({unkown_err}). Failed to open {dest_port} at {dest_ip}.")
            raise unkown_err

    def connect(self):
        self.connected = False
        try: 
            self.connected = self.client.connect() 
        except Exception as e:
            pass
        return self.connected

    def close(self):
        self.client.close()

    def tx_pattern_enable(self, reader_index, pattern_name, one_shot):
        """Send msg to enable a pattern"""
        address = f"/channel/{reader_index}/pattern/{pattern_name}/enable"
        if not self.connected:
            print(
                f'OSC port not open. Failed to send msg: {address}/{"T"}, one shot: {one_shot}'
            )
        else:
            try:
                self.client.send_message(address, "T\n")
                print(f'Sent msg: {address}/{"T"}, one shot: {one_shot}')
            except Exception as e:
                print(f'failed to send message: {e}')
                self.connected = False

    def tx_pattern_disable(self, reader_index, pattern_name):
        """Send msg to disable a pattern"""
        address = f"/channel/{reader_index}/pattern/{pattern_name}/enable"
        if not self.connected:
            print(f'OSC port not open. Failed to send msg: {address}/{"F"}')
        else:
            try:
                self.client.send_message(address, "F\n")
                print(f'Sent msg: {address}/{"F"}')
            except Exception as e: #errno 32 is broken pipe, errno 104 is connection reset by peer
                print(f'failed to send message: {e}')
                self.connected = False


class NfcController:
    """
    NFC Controller -- supports polling multiple readers
    """

    def __init__(self, client) -> None:
        self.readers = []

        self.chromatik_client = client

        self.connect = False

        ch_config_file = open("configs/channel_mapping.json", "r")
        self.ch_config = json.load(ch_config_file)

        self.gpio_if = lgpio.gpiochip_open(0)

    def close_all(self):
        """
        Close all detected NFC readers. If reader is not closed correctly, it
        will not initialize correctly on the next run due issue on PN532
        """
        for nfc_reader in self.readers:
            nfc_reader.clf.close()
            nfc_reader.set_led(False)
        lgpio.gpiochip_close(self.gpio_if)
        self.chromatik_client.close()
        print("***Closed all readers***")

    def discover_readers_from_config(self): 
        """
        Load configuration data from a hard coded config file. 
        To automatically discover readers, use "discover readers"
        """
        print("***Discovering Readers***")
        reader_num = 0
        for key in self.ch_config: 
            try:
                path = "tty:" + self.ch_config[key]["ftdi_sn"]
                clf = nfc.ContactlessFrontend(path)
                print(f'Found {key} at {path}') 
                self.readers.append(NfcReader(clf, self.ch_config[key]["led_gpio"], self.gpio_if, self.chromatik_client, reader_num))
                reader_num = reader_num + 1
            except OSError as error:
                if error.errno == errno.ENODEV:
                    print(f'Reader on {path} unresponsive. Power cycle reader and try again.')
                else: 
                    print(f'Unknown error: {error}. Unable to find device at {path}')

    def discover_readers_auto(self):
        """Discover readers connected via FTDI USB to serial cables"""
        print("***Discovering Readers***")
        ftdi_cables = nfc.clf.transport.TTY.find("ttyUSB")
        if ftdi_cables is not None:
            for dev in ftdi_cables[0]:
                path = f"tty:{dev[8:]}"
                try:
                    clf = nfc.ContactlessFrontend(path)
                    print(f"Found device: {clf.device}")
                    self.readers.append(NfcReader(clf, self.ch_config[key]["led_gpio"], self.gpio_if))
                except IOError as error:
                    if error.errno == errno.ENODEV:
                        print(
                            f"Reader on {path} unresponsive. Power cycle reader and try again"
                        )
                    else:
                        print(f"Unkown error: {error}")


    def loop(self):
        """Poll each reader for a card, print the tag"""
        print("***Polling***")

        for reader in self.readers:
            if reader.activated:
                reader.set_led(not reader.led_enabled)

        if not self.chromatik_client.connected:
            try: 
                print("Missing TCP connection. Retrying...")
                self.chromatik_client.connect() # retry
                if self.chromatik_client.connected:
                    print("Reconnected")
            except:
                pass

if __name__ == "__main__":
    print("***CTRL+C or pskill python to exit***")
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", default="127.0.0.1", help="The ip to listen on")
    parser.add_argument("--port", type=int, default=7777, help="The port to listen on")
    parser.add_argument(
        "--quiet", type=bool, default=False, help="The port to listen on"
    )
    args = parser.parse_args()

    success = False
    client = ChromatikOcsClient(args.ip, args.port)
    success = client.connected
    while not success and not args.quiet:
        print("Waiting for TCP server...")
        try:
            success = client.connect()
        except Exception as e:
            print(f'Failed to connect: {e}')
        time.sleep(1)

    controller = NfcController(client)

    controller.discover_readers_from_config()

    if len(controller.readers) < 4:
        print("***Not all devices found. Exiting***")
        controller.close_all()
        quit()

    handler = Sighandler()
    signal.signal(signal.SIGINT, handler.signal_handler)
    signal.signal(signal.SIGTERM, handler.signal_handler)

    while not handler.sigint:
        try:
            controller.loop()
            time.sleep(0.3)
        except Exception as uknown_exception:
            controller.close_all()
            quit()
    controller.close_all()
