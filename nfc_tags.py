"""
Definition
"""
import ndef


class ElderMothertagBase():
    """
    All tags must have some respresentation on whether they are one-
    shot and the name of the pattern
    """
    def __init__(self) -> None:
        self.one_shot = False
        self.pattern_name = ""

    def is_one_shot(self):
        """Return if tag is one shot"""
        return self.one_shot

    def get_pattern(self):
        """Return pattern name as a string"""
        return self.pattern_name


class CustomTextTag(ElderMothertagBase):
    """NFC tag with an NDEF record describing its type"""

    def __init__(self, tag):
        ElderMothertagBase.__init__(self)
        self.tag = tag
        self.valid_header = False
        if tag.ndef is not None:
            record = tag.ndef.records[0]
            if isinstance(record, ndef.TextRecord):
                self.parse_record(record)

    def parse_record(self, record):
        """Update internal data based on provided NDEF text record string"""
        self.tag_data = record.text.split(";")
        self.valid_header = self.tag_data[0] == "eldermother"
        self.pattern = self.tag_data[1].split(":")[1]
        self.one_shot = self.tag_data[2].split(":")[1] in ["yes", "y", "true"]

    def is_header_valid(self):
        """Return true if the NDEF record header matches the expected string"""
        return self.valid_header

    def get_pattern(self):
        """Return the patter as a string"""
        return self.pattern_name

    def is_one_shot(self):
        """return True if card is of type one-shot"""
        return self.one_shot
