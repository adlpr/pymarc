"The pymarc.field file."

import logging

from six import Iterator
from six import text_type

from pymarc.constants import SUBFIELD_INDICATOR, END_OF_FIELD
from pymarc.marc8 import marc8_to_unicode


class Field(Iterator):
    """
    Field() pass in the field tag, indicators and subfields for the tag.

        field = Field(
            tag = '245',
            indicators = ['0','1'],
            subfields = [
                'a', 'The pragmatic programmer : ',
                'b', 'from journeyman to master /',
                'c', 'Andrew Hunt, David Thomas.',
            ])

    If you want to create a control field, don't pass in the indicators
    and use a data parameter rather than a subfields parameter:

        field = Field(tag='001', data='fol05731351')

    """
    def __init__(self, tag, indicators=None, subfields=None, data=u''):
        if indicators == None:
            indicators = []
        if subfields == None:
            subfields = []
        indicators = [text_type(x) for x in indicators]

        # attempt to normalize integer tags if necessary
        try:
            self.tag = '%03i' % int(tag)
        except ValueError:
            self.tag = '%03s' % tag

        # assume controlfields are numeric only; replicates ruby-marc behavior
        if self.is_control_field():
            self.data = data
        else:
            self.indicator1, self.indicator2 = self.indicators = indicators
            self.subfields = list(subfields)

    def __iter__(self):
        self.__pos = 0
        return self

    def __str__(self):
        """
        A Field object in a string context will return the tag, indicators
        and subfield as a string. This follows MARCMaker format; see [1]
        and [2] for further reference. Special character mnemonic strings
        have yet to be implemented (see [3]), so be forewarned. Note also
        for complete MARCMaker compatibility, you will need to change your
        newlines to DOS format ('\r\n').

        [1] http://www.loc.gov/marc/makrbrkr.html#mechanics
        [2] http://search.cpan.org/~eijabb/MARC-File-MARCMaker/
        [3] http://www.loc.gov/marc/mnemonics.html
        """
        if self.is_control_field():
            text = '=%s  %s' % (self.tag, self.data.replace(' ','\\'))
        else:
            text = '=%s  ' % (self.tag)
            for indicator in self.indicators:
                if indicator in (' ','\\'):
                    text += '\\'
                else:
                    text += '%s' % indicator
            for subfield in self:
                text += ('$%s%s' % subfield)
        return text

    def __getitem__(self, subfield):
        """
        Retrieve the first subfield with a given subfield code in a field:

            field['a']

        Handy for quick lookups.
        """
        subfields = self.get_subfields(subfield)
        if len(subfields) > 0:
            return subfields[0]
        return None

    def __contains__(self, subfield):
        """
        Allows a shorthand test of field membership:

            'a' in field

        """
        subfields = self.get_subfields(subfield)
        return len(subfields) > 0

    def __setitem__(self, code, value):
        """
        Set the values of the subfield code in a field:

            field['a'] = 'value'

        Raises KeyError if there is more than one subfield code.

        If code does not yet exist, adds new subfield.
        """
        subfields = self.get_subfields(code)
        if len(subfields) > 1:
            raise KeyError("more than one code '%s'" % code)
        elif len(subfields) == 0:
            self.add_subfield(code, value)
        else:
            num_code = len(self.subfields)//2
            while num_code >= 0:
                if self.subfields[(num_code*2)-2] == code:
                    self.subfields[(num_code*2)-1] = value
                    break
                num_code -= 1

    def __next__(self):
        """
        Needed for iteration.
        """
        if not hasattr(self, 'subfields'):
            raise StopIteration
        while self.__pos < len(self.subfields):
            subfield = (self.subfields[ self.__pos ],
                self.subfields[ self.__pos+1 ])
            self.__pos += 2
            return subfield
        raise StopIteration

    def __eq__(self, other):
        """
        Fields are equivalent if they contain all the same data as another Field.
        """
        if not isinstance(other, Field) or other.tag != self.tag:
            return False
        if self.is_control_field():
            return other.data == self.data
        return other.indicators == self.indicators and other.subfields == self.subfields

    def value(self):
        """
        Returns the field as a string without tag, indicators, and
        subfield indicators.
        """
        if self.is_control_field():
            return self.data
        value_list = []
        for subfield in self:
            value_list.append(subfield[1].strip())
        return ' '.join(value_list)

    def count(self, code):
        """
        Returns the number of subfields with given code.
        """
        return len([subf for subf in self if subf[0] == code])

    def get_subfields(self, *codes, with_codes=False):
        """
        get_subfields() accepts one or more subfield codes and returns
        a list of subfield values (or, if with_codes is True, a list of
        tuples with subfield codes and values). The order of the subfield values
        in the list will be the order that they appear in the field.

        If no code is specified, all subfields are returned.

            field.get_subfields('a')
            field.get_subfields('a', 'b', 'z')
        """
        values = []
        for subfield in self:
            if subfield[0] in codes or not codes:
                values.append(subfield if with_codes else subfield[1])
        return values

    def subfields_as_dict(self):
        """
        Returns this field's subfields in the form:
            { code : [val1, val2, ...], ... }
        Loses order information, but useful for surveying.
        """
        subfields_dict = {}
        for code, val in self:
            if code not in subfields_dict:
                subfields_dict[code] = []
            subfields_dict[code].append(val)
        return subfields_dict

    def add_subfield(self, code, value):
        """
        Adds a subfield code/value pair to the field.

            field.add_subfield('u', 'http://www.loc.gov')
        """
        self.subfields.append(code)
        self.subfields.append(value)

    def delete_subfield(self, code, match_value=None):
        """
        Deletes the first subfield with the specified 'code' (and value if specified),
        and returns its value:

            field.delete_subfield('a')

        If no subfield is found with the specified code (and value if specified),
        None is returned.
        """
        for i, subf_code in enumerate(self.subfields):
            if i % 2 == 0 and code == subf_code:
                if match_value is None or self.subfields[i+1] == match_value:
                    self.subfields.pop(i)         # code
                    return self.subfields.pop(i)  # value
        return None

    def delete_all_subfields(self, code):
        """
        Repeats the delete_subfield method until all subfields of given code are deleted.
        """
        while self.delete_subfield(code):
            continue

    def change_code(self, from_code, to_code):
        """
        Converts all subfield tags of a given code to another code.
        """
        self.subfields = [val if i%2 else {from_code:to_code}.get(val, val) for i, val in enumerate(self.subfields)]

    def sort(self, key=lambda code: code):
        """
        Sorts subfields according to input function (alphabetic by default).
        """
        self.subfields = [ item for tuple in \
                          sorted( zip(self.subfields[::2],self.subfields[1::2]), \
                                  key=key ) \
                          for item in tuple ]

    def is_control_field(self):
        """
        Returns true or false if the field is considered a control field.
        Control fields lack indicators and subfields.
        """
        return self.tag < '010' and self.tag.isdigit()

    def as_marc(self, encoding):
        """
        used during conversion of a field to raw marc
        """
        if self.is_control_field():
            return (self.data + END_OF_FIELD).encode(encoding)
        marc = self.indicator1 + self.indicator2
        for subfield in self:
            marc += SUBFIELD_INDICATOR + subfield[0] + subfield[1]

        return (marc + END_OF_FIELD).encode(encoding)

    # alias for backwards compatibility
    as_marc21 = as_marc

    def format_field(self):
        """
        Returns the field as a string without tag, indicators, and
        subfield indicators. Like pymarc.Field.value(), but prettier
        (adds spaces, formats subject headings).
        """
        if self.is_control_field():
            return self.data
        fielddata = ''
        for subfield in self:
            if subfield[0] == '6':
                continue
            if not self.is_subject_field():
                fielddata += ' %s' % subfield[1]
            else:
                if subfield[0] not in ('v', 'x', 'y', 'z'):
                    fielddata += ' %s' % subfield[1]
                else: fielddata += ' -- %s' % subfield[1]
        return fielddata.strip()

    def is_subject_field(self):
        """
        Returns True or False if the field is considered a subject
        field.  Used by format_field.
        """
        if self.tag.startswith('6'):
            return True
        return False


class RawField(Field):
    """
    MARC field that keeps data in raw, undecoded byte strings.

    Should only be used when input records are wrongly encoded.
    """
    def as_marc(self, encoding=None):
        """
        used during conversion of a field to raw marc
        """
        if encoding is not None:
            logging.warn("Attempt to force a RawField into encoding %s", encoding)
        if self.is_control_field():
            return self.data + END_OF_FIELD
        marc = self.indicator1.encode('ascii') + self.indicator2.encode('ascii')
        for subfield in self:
            marc += SUBFIELD_INDICATOR.encode('ascii') + subfield[0] + subfield[1]
        return marc + END_OF_FIELD


def map_marc8_field(f):
    if f.is_control_field():
        f.data = marc8_to_unicode(f.data)
    else:
        f.subfields = map(marc8_to_unicode, f.subfields)
    return f
