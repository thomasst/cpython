
"""
csv.py - read/write/investigate CSV files
"""

import re
from _csv import Error, __version__, writer, reader, register_dialect, \
                 unregister_dialect, get_dialect, list_dialects, \
                 QUOTE_MINIMAL, QUOTE_ALL, QUOTE_NONNUMERIC, QUOTE_NONE, \
                 __doc__

__all__ = [ "QUOTE_MINIMAL", "QUOTE_ALL", "QUOTE_NONNUMERIC", "QUOTE_NONE",
            "Error", "Dialect", "excel", "excel_tab", "reader", "writer",
            "register_dialect", "get_dialect", "list_dialects", "Sniffer",
            "unregister_dialect", "__version__", "DictReader", "DictWriter" ]

class Dialect:
    _name = ""
    _valid = False
    # placeholders
    delimiter = None
    quotechar = None
    escapechar = None
    doublequote = None
    skipinitialspace = None
    lineterminator = None
    quoting = None

    def __init__(self):
        if self.__class__ != Dialect:
            self._valid = True
        errors = self._validate()
        if errors != []:
            raise Error, "Dialect did not validate: %s" % ", ".join(errors)

    def _validate(self):
        errors = []
        if not self._valid:
            errors.append("can't directly instantiate Dialect class")

        if self.delimiter is None:
            errors.append("delimiter character not set")
        elif (not isinstance(self.delimiter, str) or
              len(self.delimiter) > 1):
            errors.append("delimiter must be one-character string")

        if self.quotechar is None:
            if self.quoting != QUOTE_NONE:
                errors.append("quotechar not set")
        elif (not isinstance(self.quotechar, str) or
              len(self.quotechar) > 1):
            errors.append("quotechar must be one-character string")

        if self.lineterminator is None:
            errors.append("lineterminator not set")
        elif not isinstance(self.lineterminator, str):
            errors.append("lineterminator must be a string")

        if self.doublequote not in (True, False):
            errors.append("doublequote parameter must be True or False")

        if self.skipinitialspace not in (True, False):
            errors.append("skipinitialspace parameter must be True or False")

        if self.quoting is None:
            errors.append("quoting parameter not set")

        if self.quoting is QUOTE_NONE:
            if (not isinstance(self.escapechar, (unicode, str)) or
                len(self.escapechar) > 1):
                errors.append("escapechar must be a one-character string or unicode object")

        return errors

class excel(Dialect):
    delimiter = ','
    quotechar = '"'
    doublequote = True
    skipinitialspace = False
    lineterminator = '\r\n'
    quoting = QUOTE_MINIMAL
register_dialect("excel", excel)

class excel_tab(excel):
    delimiter = '\t'
register_dialect("excel-tab", excel_tab)


class DictReader:
    def __init__(self, f, fieldnames, restkey=None, restval=None,
                 dialect="excel", *args):
        self.fieldnames = fieldnames    # list of keys for the dict
        self.restkey = restkey          # key to catch long rows
        self.restval = restval          # default value for short rows
        self.reader = reader(f, dialect, *args)

    def __iter__(self):
        return self

    def next(self):
        row = self.reader.next()
        # unlike the basic reader, we prefer not to return blanks,
        # because we will typically wind up with a dict full of None
        # values
        while row == []:
            row = self.reader.next()
        d = dict(zip(self.fieldnames, row))
        lf = len(self.fieldnames)
        lr = len(row)
        if lf < lr:
            d[self.restkey] = row[lf:]
        elif lf > lr:
            for key in self.fieldnames[lr:]:
                d[key] = self.restval
        return d


class DictWriter:
    def __init__(self, f, fieldnames, restval="", extrasaction="raise",
                 dialect="excel", *args):
        self.fieldnames = fieldnames    # list of keys for the dict
        self.restval = restval          # for writing short dicts
        if extrasaction.lower() not in ("raise", "ignore"):
            raise ValueError, \
                  ("extrasaction (%s) must be 'raise' or 'ignore'" %
                   extrasaction)
        self.extrasaction = extrasaction
        self.writer = writer(f, dialect, *args)

    def _dict_to_list(self, rowdict):
        if self.extrasaction == "raise":
            for k in rowdict.keys():
                if k not in self.fieldnames:
                    raise ValueError, "dict contains fields not in fieldnames"
        return [rowdict.get(key, self.restval) for key in self.fieldnames]

    def writerow(self, rowdict):
        return self.writer.writerow(self._dict_to_list(rowdict))

    def writerows(self, rowdicts):
        rows = []
        for rowdict in rowdicts:
            rows.append(self._dict_to_list(rowdict))
        return self.writer.writerows(rows)


class Sniffer:
    '''
    "Sniffs" the format of a CSV file (i.e. delimiter, quotechar)
    Returns a csv.Dialect object.
    '''
    def __init__(self, sample = 16 * 1024):
        # in case there is more than one possible delimiter
        self.preferred = [',', '\t', ';', ' ', ':']

        # amount of data (in bytes) to sample
        self.sample = sample


    def sniff(self, fileobj):
        """
        Takes a file-like object and returns a dialect (or None)
        """

        self.fileobj = fileobj

        data = fileobj.read(self.sample)

        quotechar, delimiter, skipinitialspace = \
                   self._guessQuoteAndDelimiter(data)
        if delimiter is None:
            delimiter, skipinitialspace = self._guessDelimiter(data)

        class Dialect(csv.Dialect):
            _name = "sniffed"
            lineterminator = '\r\n'
            quoting = csv.QUOTE_MINIMAL
            # escapechar = ''
            doublequote = False
        Dialect.delimiter = delimiter
        Dialect.quotechar = quotechar
        Dialect.skipinitialspace = skipinitialspace

        self.dialect = Dialect
        return self.dialect


    def hasHeaders(self):
        return self._hasHeaders(self.fileobj, self.dialect)


    def register_dialect(self, name = 'sniffed'):
        csv.register_dialect(name, self.dialect)


    def _guessQuoteAndDelimiter(self, data):
        """
        Looks for text enclosed between two identical quotes
        (the probable quotechar) which are preceded and followed
        by the same character (the probable delimiter).
        For example:
                         ,'some text',
        The quote with the most wins, same with the delimiter.
        If there is no quotechar the delimiter can't be determined
        this way.
        """

        matches = []
        for restr in ('(?P<delim>[^\w\n"\'])(?P<space> ?)(?P<quote>["\']).*?(?P=quote)(?P=delim)', # ,".*?",
                      '(?:^|\n)(?P<quote>["\']).*?(?P=quote)(?P<delim>[^\w\n"\'])(?P<space> ?)',   #  ".*?",
                      '(?P<delim>>[^\w\n"\'])(?P<space> ?)(?P<quote>["\']).*?(?P=quote)(?:$|\n)',  # ,".*?"
                      '(?:^|\n)(?P<quote>["\']).*?(?P=quote)(?:$|\n)'):                            #  ".*?" (no delim, no space)
            regexp = re.compile(restr, re.S | re.M)
            matches = regexp.findall(data)
            if matches:
                break

        if not matches:
            return ('', None, 0) # (quotechar, delimiter, skipinitialspace)

        quotes = {}
        delims = {}
        spaces = 0
        for m in matches:
            n = regexp.groupindex['quote'] - 1
            key = m[n]
            if key:
                quotes[key] = quotes.get(key, 0) + 1
            try:
                n = regexp.groupindex['delim'] - 1
                key = m[n]
            except KeyError:
                continue
            if key:
                delims[key] = delims.get(key, 0) + 1
            try:
                n = regexp.groupindex['space'] - 1
            except KeyError:
                continue
            if m[n]:
                spaces += 1

        quotechar = reduce(lambda a, b, quotes = quotes:
                           (quotes[a] > quotes[b]) and a or b, quotes.keys())

        if delims:
            delim = reduce(lambda a, b, delims = delims:
                           (delims[a] > delims[b]) and a or b, delims.keys())
            skipinitialspace = delims[delim] == spaces
            if delim == '\n': # most likely a file with a single column
                delim = ''
        else:
            # there is *no* delimiter, it's a single column of quoted data
            delim = ''
            skipinitialspace = 0

        return (quotechar, delim, skipinitialspace)


    def _guessDelimiter(self, data):
        """
        The delimiter /should/ occur the same number of times on
        each row. However, due to malformed data, it may not. We don't want
        an all or nothing approach, so we allow for small variations in this
        number.
          1) build a table of the frequency of each character on every line.
          2) build a table of freqencies of this frequency (meta-frequency?),
             e.g.  'x occurred 5 times in 10 rows, 6 times in 1000 rows,
             7 times in 2 rows'
          3) use the mode of the meta-frequency to determine the /expected/
             frequency for that character
          4) find out how often the character actually meets that goal
          5) the character that best meets its goal is the delimiter
        For performance reasons, the data is evaluated in chunks, so it can
        try and evaluate the smallest portion of the data possible, evaluating
        additional chunks as necessary.
        """

        data = filter(None, data.split('\n'))

        ascii = [chr(c) for c in range(127)] # 7-bit ASCII

        # build frequency tables
        chunkLength = min(10, len(data))
        iteration = 0
        charFrequency = {}
        modes = {}
        delims = {}
        start, end = 0, min(chunkLength, len(data))
        while start < len(data):
            iteration += 1
            for line in data[start:end]:
                for char in ascii:
                    metafrequency = charFrequency.get(char, {})
                    # must count even if frequency is 0
                    freq = line.strip().count(char)
                    # value is the mode
                    metafrequency[freq] = metafrequency.get(freq, 0) + 1
                    charFrequency[char] = metafrequency

            for char in charFrequency.keys():
                items = charFrequency[char].items()
                if len(items) == 1 and items[0][0] == 0:
                    continue
                # get the mode of the frequencies
                if len(items) > 1:
                    modes[char] = reduce(lambda a, b: a[1] > b[1] and a or b,
                                         items)
                    # adjust the mode - subtract the sum of all
                    # other frequencies
                    items.remove(modes[char])
                    modes[char] = (modes[char][0], modes[char][1]
                                   - reduce(lambda a, b: (0, a[1] + b[1]),
                                            items)[1])
                else:
                    modes[char] = items[0]

            # build a list of possible delimiters
            modeList = modes.items()
            total = float(chunkLength * iteration)
            # (rows of consistent data) / (number of rows) = 100%
            consistency = 1.0
            # minimum consistency threshold
            threshold = 0.9
            while len(delims) == 0 and consistency >= threshold:
                for k, v in modeList:
                    if v[0] > 0 and v[1] > 0:
                        if (v[1]/total) >= consistency:
                            delims[k] = v
                consistency -= 0.01

            if len(delims) == 1:
                delim = delims.keys()[0]
                skipinitialspace = (data[0].count(delim) ==
                                    data[0].count("%c " % delim))
                return (delim, skipinitialspace)

            # analyze another chunkLength lines
            start = end
            end += chunkLength

        if not delims:
            return ('', 0)

        # if there's more than one, fall back to a 'preferred' list
        if len(delims) > 1:
            for d in self.preferred:
                if d in delims.keys():
                    skipinitialspace = (data[0].count(d) ==
                                        data[0].count("%c " % d))
                    return (d, skipinitialspace)

        # finally, just return the first damn character in the list
        delim = delims.keys()[0]
        skipinitialspace = (data[0].count(delim) ==
                            data[0].count("%c " % delim))
        return (delim, skipinitialspace)


    def _hasHeaders(self, fileobj, dialect):
        # Creates a dictionary of types of data in each column. If any
        # column is of a single type (say, integers), *except* for the first
        # row, then the first row is presumed to be labels. If the type
        # can't be determined, it is assumed to be a string in which case
        # the length of the string is the determining factor: if all of the
        # rows except for the first are the same length, it's a header.
        # Finally, a 'vote' is taken at the end for each column, adding or
        # subtracting from the likelihood of the first row being a header.

        def seval(item):
            """
            Strips parens from item prior to calling eval in an
            attempt to make it safer
            """
            return eval(item.replace('(', '').replace(')', ''))

        # rewind the fileobj - this might not work for some file-like
        # objects...
        fileobj.seek(0)

        reader = csv.reader(fileobj,
                            delimiter = dialect.delimiter,
                            quotechar = dialect.quotechar,
                            skipinitialspace = dialect.skipinitialspace)

        header = reader.next() # assume first row is header

        columns = len(header)
        columnTypes = {}
        for i in range(columns): columnTypes[i] = None

        checked = 0
        for row in reader:
            # arbitrary number of rows to check, to keep it sane
            if checked > 20:
                break
            checked += 1

            if len(row) != columns:
                continue # skip rows that have irregular number of columns

            for col in columnTypes.keys():
                try:
                    try:
                        # is it a built-in type (besides string)?
                        thisType = type(seval(row[col]))
                    except OverflowError:
                        # a long int?
                        thisType = type(seval(row[col] + 'L'))
                        thisType = type(0) # treat long ints as int
                except:
                    # fallback to length of string
                    thisType = len(row[col])

                if thisType != columnTypes[col]:
                    if columnTypes[col] is None: # add new column type
                        columnTypes[col] = thisType
                    else:
                        # type is inconsistent, remove column from
                        # consideration
                        del columnTypes[col]

        # finally, compare results against first row and "vote"
        # on whether it's a header
        hasHeader = 0
        for col, colType in columnTypes.items():
            if type(colType) == type(0): # it's a length
                if len(header[col]) != colType:
                    hasHeader += 1
                else:
                    hasHeader -= 1
            else: # attempt typecast
                try:
                    eval("%s(%s)" % (colType.__name__, header[col]))
                except:
                    hasHeader += 1
                else:
                    hasHeader -= 1

        return hasHeader > 0
