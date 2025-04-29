#!/usr/bin/env python3


"""
To use this class, create the object with the name of a logfile as an
argument:
  log = FlightLog('log_161119_154619_KEYW.csv')

This reads the file headers and figures out if it's an Avidyne or
Garmin data file.

To see what data is in the log:
  log.vendor - 'garmin' or 'avidyne'  (maybe more in the future?)
  log.columns - list of names of columns
  log.column_idx - dictionary of column name mapping to column index

To extract data:
  data = log.read(['elapsed', 'Latitude', 'Longitude'])

This will read the full file, parsing and converting
each column listed, and return a list of lists:
  data[0] = 'elapsed' column data
  data[1] = 'Latitude' column data
  data[2] = 'Longitude' column data

Avidyne and Garmin use different names for the same data, so there
are methods on the FlightLog object to provide the appropriate name
for the given file.

  log.col_latitude() - latitude column
  log.col_longitude() - longitude column
  log.col_CHT() - list of cylinder head temperature columns
  log.col_rpm() - engine RPM column

There are also two special computed columns for time data.
  'timestamp' - an absolute time as a datetime object.
  'elapsed' - time since the beginning of the log file in seconds.

Some oddities to know about:
 - Some logfiles start with blank timestamps and latitude/longitudes, until
   the GPS gets a fix. Then they work. But sometime the latitude/longitude
   blanks out again briefly (for example, line 7 of samples/garmin-sr22t-log_161119_154619_KEYW.csv)

 - timestamps are not strictly increasing, at least in Garmin files.
   sometimes the logs contain multiple entries in the same
   second. Also Garmin files generally log one entry per second, but
   occasionally they skip a second or two.  In Avidyne files I haven't
   yet found a case where they don't log exactly once every six
   seconds.
"""


import csv
from datetime import datetime
from datetime import timedelta
import re
import sys


# storing these in variables to avoid typos
VENDOR_AVIDYNE = 'avidyne'
VENDOR_GARMIN = 'garmin'
COLUMN_NAME_TIMESTAMP = 'timestamp'
COLUMN_NAME_ELAPSED = 'elapsed'


def parse_float(string):
    """
    Parse a float or return None on failure.
    This is to handle data where null entries are encoded as empty strings.
    """
    try:
        return float(string)
    except ValueError:
        return None


def parse_int(string):
    """
    Parse an integer or return None on failure.
    """
    try:
        return int(string)
    except ValueError:
        return None


# regular expression for matching unsigned integers
INT_RE = re.compile(r'\d+')


def parse_int_tuple(string):
    """
    Given a string containing multiple positive integers, return a tuple
    of them.  "2025-10-31" -> (2025, 10, 31)
    """
    return tuple(int(int_str) for int_str in INT_RE.findall(string))


class ColumnDef:
    """
    Encapsulates a column name and data type.
    All inputs are strings. The data type determines what those strings
    should be parsed into. Failed parses result in values of None.
    """
    
    def __init__(self, name, column_type = str):
        """
        column_type: int, float, or str
          if str then no conversion is done, just strip()
        """
        self.name = name
        self.column_type = column_type

        if self.column_type == float:
            self.parse = parse_float
        elif self.column_type == int:
            self.parse = parse_int
        elif self.column_type == str:
            self.parse = lambda x: x.strip()
        else:
            raise FlightLogException(f'ColumnDef unknown column_type: {column_type}')

    def __repr__(self):
        return f'ColumnDef({self.name!r}, {self.column_type.__name__})'


# List of recognized columns in Avidyne logs.
# There may be more columns, and they may not be in this order.
# For example, a Diamond DA-20 has a four-cylinder engine so it
# won't have E5, E6, C5, or C6.
AVIDYNE_COLUMNS = [
    ColumnDef("TIME"),
    ColumnDef("LAT", float),
    ColumnDef("LON", float),
    ColumnDef("PALT", int), # pressure altitude (only on turbo)
    ColumnDef("DALT", int), # density altitude (only on turbo)
    ColumnDef("E1", int),
    ColumnDef("E2", int),
    ColumnDef("E3", int),
    ColumnDef("E4", int),
    ColumnDef("E5", int),  # 5 and 6 should be optional to support
    ColumnDef("E6", int),  # 4 cylinder engines
    ColumnDef("C1", int),
    ColumnDef("C2", int),
    ColumnDef("C3", int),
    ColumnDef("C4", int),
    ColumnDef("C5", int),
    ColumnDef("C6", int),
    ColumnDef("OILT", int),
    ColumnDef("OILP", int),
    ColumnDef("RPM", int),
    ColumnDef("OAT", int),  # outside air temp (degrees C)
    ColumnDef("MAP", float),  # manifold pressure (in inches Hg)
    ColumnDef("FF", float),  # fuel flow (in gph)
    ColumnDef("USED", float),  # cumulative gallons fuel used
    ColumnDef("AMP1", int),
    ColumnDef("AMP2", int),
    ColumnDef("AMPB", int),
    ColumnDef("MBUS", float),
    ColumnDef("EBUS", float),
    ColumnDef("TIT", int),  # turbine inlet temperature (only on turbo)
]


# index AVIDYNE_COLUMNS
AVIDYNE_COLUMN_TABLE = {obj.name: obj for obj in AVIDYNE_COLUMNS}


# as a quick sanity check, look for these columns and reject files
# that don't have them
AVIDYNE_REQUIRED_COLUMNS = ['TIME', 'LAT', 'E1', 'MAP', 'FF']


"""
List of recognized columns in Garmin logs.

See "FLIGHT DATA LOGGING" in Garmin manual.
  https://static.garmin.com/pumac/190-00820-12_B.pdf

This list is a subset of the columns in the data files. There are a few
other columns that either I don't understand or don't seem useful.
"""
GARMIN_COLUMNS = [
    ColumnDef('Lcl Date'), # format YYYY-MM-DD
    ColumnDef('Lcl Time'), # format HH:MM:SS
    ColumnDef('UTCOfst'), # format: [+-]hh:mm"
    ColumnDef('AtvWpt'),  # active waypoint
    ColumnDef('Latitude', float),  # North is positive
    ColumnDef('Longitude', float),  # East is positive
    ColumnDef('AltB', float),  # baro-corrected altitude (feet)
    ColumnDef('BaroA', float),  # altimeter setting (inches Hg)
    ColumnDef('AltMSL', ),  # GPS-derived altitude (feet)
    ColumnDef('OAT', float),  # outside air temperature (degrees C)
    ColumnDef('IAS', float),  # indicated airspeed (knots)
    ColumnDef('GndSpd', float), # ground speed (knots)
    ColumnDef('VSpd', float), # vertical speed (feet / minute)
    ColumnDef('Pitch', float), # pitch (degrees)
    ColumnDef('Roll', float),  # roll (degrees)
    ColumnDef('LatAc', float), # lateral acceleration / G force
    ColumnDef('NormAc', float), # vertical acceleration / G force
    ColumnDef('HDG', float),  # heading (degrees magnetic)
    ColumnDef('TRK', float),  # track (degrees magnetic)
    ColumnDef('volt1', float), # bus 1 voltage
    ColumnDef('volt2', float), # bus 2 voltage
    ColumnDef('amp1', float), # alternator 1 amperage
    ColumnDef('FQtyL', float), # left tank fuel (gallons)
    ColumnDef('FQtyR', float), # right tank fuel (gallons)
    ColumnDef('E1 FFlow', float), # fuel flow (gallons / hour)
    ColumnDef('E1 OilT', float), # oil temp (degrees F)
    ColumnDef('E1 OilP', float), # oil pressure (psi)
    ColumnDef('E1 MAP', float), # manifold pressure (inches Hg)
    ColumnDef('E1 RPM', float), # engine speed (rpms)
    ColumnDef('E1 %Pwr', float), # percent power, where 1 = 100%
    ColumnDef('E1 CHT1', float), # cylinder head temps (degrees F)
    ColumnDef('E1 CHT2', float),
    ColumnDef('E1 CHT3', float),
    ColumnDef('E1 CHT4', float),
    ColumnDef('E1 CHT5', float), # 5 and 6 should be optional to support
    ColumnDef('E1 CHT6', float), # 4 cylinder engines
    ColumnDef('E1 EGT1', float), # exhaust gas temps (degrees F)
    ColumnDef('E1 EGT2', float),
    ColumnDef('E1 EGT3', float),
    ColumnDef('E1 EGT4', float),
    ColumnDef('E1 EGT5', float),
    ColumnDef('E1 EGT6', float),
    ColumnDef('E1 TIT1', float), # turbo 1 inlet temp (degrees F)
    ColumnDef('E1 TIT2', float), # turbo 2 inlet temp (degrees F)
    
    # I'll worry about E2 columns when I get a twin
    
    ColumnDef('AltGPS', float), # GPS-derived altitude, WGS84 datum
    ColumnDef('TAS', int), # true airspeed (knots)
    ColumnDef('HSIS'), # navigation source (e.g. GPS, NAV1, or NAV2)
    ColumnDef('CRS', float), # navigation cource (degrees magnetic)
    ColumnDef('NAV1', float), # NAV1 frequency (MHz)
    ColumnDef('NAV2', float), # NAV2 frequency (MHz)
    ColumnDef('COM1', float), # COM1 frequency (MHz)
    ColumnDef('COM2', float), # COM2 frequency (MHz)
    ColumnDef('HCDI', float), # horizontal course deviation deflection
    ColumnDef('VCDI'), # vertical (glideslope) deflection
    ColumnDef('WndSpd', float), # wind aloft speed (knots)
    ColumnDef('WndDr', float), # wind aloft direction (degrees, can be negative)
    ColumnDef('WptDst', float), # distance to next waypoint
    ColumnDef('WptBrg', float), # bearing to next waypoint
    ColumnDef('MagVar', float), # magnetic variation
    ColumnDef('AfcsOn', int), # 1=autopilot on, 0=off
    ColumnDef('RollM'), # flight director roll mode: HDG, GPS, ...
    ColumnDef('PitchM'), # flight director pitch mode: PIT, ALT, ALTS, ...
    ColumnDef('RollC', float), # flight director roll commanded?
    ColumnDef('PichC', float), # flight director pitch commanded?
    ColumnDef('VSpdG', float), # GPS-derived vertical speed
    ColumnDef('GPSfix', float), # quality of GPS fix? Usually "3D"

    # columns added with an SF50 and a Garmin G3000
    # FYI "E1 FFlow" is in gallons per hour, not pounds per hour,
    # at least in the SF50.
    
    ColumnDef('AltInd', float),  # indicated altitude, replaces AltB
    ColumnDef('amp2', float),
    ColumnDef('E1 Torq', float),  # all null in SF50. Only for turboprops?
    ColumnDef('E1 NG', float),  # all null in SF50. Only for turboprops?
    ColumnDef('E1 ITT', float),  # interstage turbine temp, degrees C
    ColumnDef('E1 N1', float),  # N1 speed, where 1.0 == 100%
    ColumnDef('E1 N2', float),  # N2 speed, where 1.0 == 100%
    
]

# index GARMIN_COLUMNS
GARMIN_COLUMN_TABLE = {obj.name: obj for obj in GARMIN_COLUMNS}


# as a quick sanity check, look for these columns and reject files
# that don't have them
GARMIN_REQUIRED_COLUMNS = ['Lcl Date', 'Latitude', 'E1 FFlow', 'AfcsOn']


class ColumnReader:
    """
    Represents one output column using the input ColumnDef and the index
    of the input column, so this can extract and parse an input field
    from an input row.

    This is designed to be overridden by
    (Garmin|Avidyne)(Timestamp|Elapsed)Reader
    to generate computed columns.
    """
    
    def __init__(self, column_def, input_col_idx):
        self.column_def = column_def
        self.input_col_idx = input_col_idx

    def read(self, input_row):
        return self.column_def.parse(input_row[self.input_col_idx])

    def max_col_needed(self):
        """
        Maximum input column needed by this reader.
        Some logfiles end with a truncated row (for example, samples/garmin-sf50-log_240810_104802_KAPA.csv)
        Handle this gracefully by having each column reader know the maximum
        column that it needs, and if an input row is shorter than that, then
        consider that the end of the file.
        """
        return self.input_col_idx


class AvidyneTimestampReader(ColumnReader):
    """
    Generate timestamp column for Avidyne logs
    """
    def __init__(self, start_time, time_col_idx):
        # first timestamp in the input file
        self.start_time = start_time
        self.time_col_idx = time_col_idx
        
        # Cache a copy of a 1 day time delta, because if we use it
        # we'll use it a lot.
        # yea, yea, this is premature optimization
        self.one_day = timedelta(days=1)

    def max_col_needed(self):
        return self.time_col_idx

    def makeTimestamp(self, input_row):
        hour_minute_second = parse_int_tuple(input_row[self.time_col_idx])
        if len(hour_minute_second) != 3:
            return None
        hour, minute, second = hour_minute_second
        timestamp = datetime(self.start_time.year, 
                             self.start_time.month,
                             self.start_time.day,
                             hour, minute, second)

        # handle day wrap
        if timestamp < self.start_time:
            timestamp += self.one_day

        return timestamp
        
    def read(self, input_row):
        return self.makeTimestamp(input_row)


class AvidyneElapsedReader(AvidyneTimestampReader):
    """
    Generate elapsed column for Avidyne logs
    """
    def __init__(self, start_time, time_col_idx):
        super().__init__(start_time, time_col_idx)

    def read(self, input_row):
        now = self.makeTimestamp(input_row)
        if now == None:
            return None
        return int((now - self.start_time).total_seconds())
        
        
class GarminTimestampReader(ColumnReader):
    """
    Generate timestamp column for Garmin logs
    """
    def __init__(self, date_col_idx, time_col_idx):
        self.date_col_idx = date_col_idx
        self.time_col_idx = time_col_idx

    def max_col_needed(self):
        return max(self.date_col_idx, self.time_col_idx)

    def makeTimestamp(self, input_row):
        year_month_day = parse_int_tuple(input_row[self.date_col_idx])
        if len(year_month_day) != 3:
            return None
        hour_minute_second = parse_int_tuple(input_row[self.time_col_idx])
        if len(hour_minute_second) != 3:
            return None
        return datetime(*year_month_day, *hour_minute_second)

    def read(self, input_row):
        return self.makeTimestamp(input_row)
        
        
class GarminElapsedReader(GarminTimestampReader):
    """
    Generate elapsed column for Garmin logs
    """
    def __init__(self, start_time, date_col_idx, time_col_idx):
        super().__init__(date_col_idx, time_col_idx)
        self.start_time = start_time

    def read(self, input_row):
        now = self.makeTimestamp(input_row)
        if now == None:
            return None
        return int((now - self.start_time).total_seconds())
    

class FlightLogException(Exception):
    def __init__(self, message):
        super().__init__(message)


class FlightLog:
    """
    Parse Garmin or Avidyne flight logs.

    Common members:
      filename: name of input file
      inf: open file handle for input file
      columns: list of Column objects matching the input file
      column_idx: name->column_index dictionary
      start_time: datetime object representing the first timestamp
        in the logfile.
    """

    @staticmethod
    def open(filename):
        # read the first line to determine the format/vendor
        inf = open(filename, encoding='Latin-1', newline='')
        line1 = inf.readline()

        # pass the open file handle to avoid closing and reopening the file

        if AvidyneFlightLog.check_first_line(line1):
            # print('creating AvidyneFlightLog')
            log = AvidyneFlightLog(filename, inf)
        elif GarminFlightLog.check_first_line(line1):
            # print('creating GarminFlightLog')
            log = GarminFlightLog(filename, inf)
        else:
            inf.close()
            raise FlightLogException('Unrecognized file format')

        # make sure constructors did their job
        assert log.columns and log.column_idx

        return log


    def __init__(self, *args):
        raise FlightLogException('FlightLog class is abstract; ' +
                                 'use FlightLog.open()')

    def vendor(self):
        """
        Derived class will override this to return 'avidyne' or 'garmin'.
        """
        return None

    def _set_column_mappings(self, column_names, column_table):
        """
        Used internally.
        column_names: list of column names in the data
        column_table: dictionary of known columns
          key=name, value = Column object

        Sets self.columns and self.column_idx
        """

        def map_columns(name):
            col = column_table.get(name, None)
            if not col:
                # unknown columns will be left as strings
                col = ColumnDef(name)
            return col

        self.columns = [map_columns(name) for name in column_names]
        self.column_idx = {name: i for i, name in enumerate(column_names)}


    def col_latitude(self):
        """
        Returns the name of the column that encodes latitude.
        """
        return None


    def col_longitude(self):
        """
        Returns the name of the column that encodes longitude.
        """
        return None
    
    def col_CHT(self):
        """
        Returns a list of column names representing cylinder head
        temperatures. This is useful becuase Avidyne logs name them
        "C1", "C2", ... and Garmin logs name them "E1 CHT1", E1 CHT2", ...
        
        This should also handle logs with other than six cylinders,
        though I don't have any to test with. Even Cessna 172s have
        six cylinders. Need a sample log from a Diamond DA20.
        """
        return []

    def col_rpm(self, all_engines = False):
        """
        Returns the name of the engine RPM column.
        If all_engines is True, returns a list of the names of RPM columns
        for all engines.
        """
        return None
    
    def read(self, requested_columns):
        """
        Reads the given columns from the file, returning them
        in structure-of-arrays form, where result[k] is all values for
        column_names[k].
        """

        result = []
        column_readers = []
        n_input_cols_needed = 0
        
        n_cols = len(requested_columns)

        for name in requested_columns:
            if name == COLUMN_NAME_TIMESTAMP:
                reader = self.createTimestampColumnReader()
            elif name == COLUMN_NAME_ELAPSED:
                reader = self.createElapsedColumnReader()
            else:
                input_idx = self.column_idx.get(name, -1)
                if input_idx == -1:
                    raise FlightLogException('Column not found: ' + name)
                reader = ColumnReader(self.columns[input_idx], input_idx)

            column_readers.append(reader)
            result.append([])
            n_input_cols_needed = max(n_input_cols_needed,
                                      1 + reader.max_col_needed())

        assert self.inf
        self.inf.seek(0)

        # avidyne and garmin have three header lines
        self.inf.readline()
        self.inf.readline()
        self.inf.readline()
        line_no = 3

        reader = csv.reader(self.inf)
        for row in reader:
            if len(row) < n_input_cols_needed:
                # short row, probably end of file. skip it
                continue
            line_no += 1
            for output_idx in range(n_cols):
                try:
                    value = column_readers[output_idx].read(row)
                except Exception as e:
                    print(f'Error reading {self.filename}, line {line_no}: {e}')
                    return result
                result[output_idx].append(value)
                
        return result


class AvidyneFlightLog(FlightLog):
    
    @staticmethod
    def check_first_line(line):
        return line.startswith('Avidyne Engine Data Log')

    def __init__(self, filename, inf):
        self.filename = filename
        self.inf = inf

        # start from the top, because the first line was already read
        self.inf.seek(0)
        self.inf.readline()  # first line has already been checked

        # second line contains a timestamp that will be used later
        line2 = self.inf.readline().strip()

        # third line contains column names
        reader = csv.reader(self.inf)
        try:
            column_names = [s.strip() for s in reader.__next__()]
            first_entry = reader.__next__()
        except StopIteration:
            # __next__ failed; the file doesn't even have a full set
            # of headers
            raise FlightLogException('File is empty')

        # set self.columns and self.column_idx
        self._set_column_mappings(column_names, AVIDYNE_COLUMN_TABLE)

        for name in AVIDYNE_REQUIRED_COLUMNS:
            if name not in self.column_idx:
                raise FlightLogException(f'Log appears to be in Avidyne format, but is missing expected column "{name}"')
        
        self.start_time = self.compute_start_time(line2, first_entry)
        
    def vendor(self):
        return VENDOR_AVIDYNE
        
    def compute_start_time(self, line2, first_entry):
        """
        Avidyne logs have a date/time in line 2 of the file, but the
        first entry is that time rounded down to a mulitple of 6 seconds,
        the logfile reporting rate. For example, you'll see "1/10/07 17:37:44"
        in the second line of the file, then the first data line will have
        the timestamp "17:37:42".

        This returns a datetime object containing the date from line2 and the
        time from first_entry.
        """

        # is in month/day/year order
        header_date_time = parse_int_tuple(line2)
        assert(len(header_date_time) == 6)
        month, day, year = header_date_time[:3]

        # Avidyne logs use 2-digit years. Just in case someone has a
        # data from a really old SR20, assume a year in the range 70-99
        # is from the 20th century.
        if year >= 70:
            # Sanity check, maybe they switched to 4-digit years?
            if year > 99:
                raise FlightLogException(f'Unexpected year > 99: "{line2}"')
            year += 1900
        else:
            year += 2000
        
        # is in hour:minute:second order
        first_timestamp = parse_int_tuple(first_entry[0])
        assert(len(first_timestamp) == 3)

        return datetime(year, month, day, *first_timestamp)

    def col_latitude(self):
        return 'LAT'

    def col_longitude(self):
        return 'LON'

    def col_CHT(self):
        cht_re = re.compile(r'C\d')
        return [name for name in self.column_idx.keys() if cht_re.match(name)]

    def col_rpm(self, all_engines = False):
        name = 'RPM'
        return [name] if all_engines else name

    def createTimestampColumnReader(self):
        time_col = self.column_idx.get('TIME', -1)
        if time_col == -1:
            raise FlightLogException('Avidyne log missing "TIME" column')
        return AvidyneTimestampReader(self.start_time, time_col)

    def createElapsedColumnReader(self):
        time_col = self.column_idx.get('TIME', -1)
        if time_col == -1:
            raise FlightLogException('Avidyne log missing "TIME" column')
        return AvidyneElapsedReader(self.start_time, time_col)


class GarminFlightLog(FlightLog):
    
    @staticmethod
    def check_first_line(line):
        return line.startswith('#airframe_info, log_version="1.0')

    def __init__(self, filename, inf):
        self.filename = filename
        self.inf = inf
        
        # start from the top, because the first line was already read
        self.inf.seek(0)
        self.inf.readline()  # first line has already been checked

        # second line contains units for each column
        self.inf.readline()

        # third line contains column names
        reader = csv.reader(self.inf)
        try:
            column_names = [s.strip() for s in reader.__next__()]
        except StopIteration:
            # __next__ failed; the file doesn't even have a full set
            # of headers
            raise FlightLogException('File is empty')

        # set self.columns and self.column_idx
        self._set_column_mappings(column_names, GARMIN_COLUMN_TABLE)

        for name in GARMIN_REQUIRED_COLUMNS:
            if name not in self.column_idx:
                raise FlightLogException(f'Log appears to be in Garmin format, but is missing expected column "{name}"')
        
        self.start_time = self.compute_start_time(reader)
        
    def vendor(self):
        return VENDOR_GARMIN

    def compute_start_time(self, reader):
        """
        Garmin logs occasionally start with null timestamps,
        perhaps because the system doesn't log anything until the GPS
        has a fix and the time is known to be precise.

        This reads the file until a non-null timestamp is found.
        None is returned if no entry contains a valid timestamp (for example,
        if the power was on briefly while in a hangar, and the GPS never
        got a fix).
        """
        for row in reader:
            year_month_day = parse_int_tuple(row[0])
            if len(year_month_day) != 0:
                assert(len(year_month_day) == 3)
                hour_minute_second = parse_int_tuple(row[1])
                assert(len(hour_minute_second) == 3)
                
                return datetime(*year_month_day, *hour_minute_second)
            
        return None

    def col_latitude(self):
        return 'Latitude'

    def col_longitude(self):
        return 'Longitude'

    def col_CHT(self):
        cht_re = re.compile(r'E\d CHT\d')
        return [name for name in self.column_idx.keys() if cht_re.match(name)]

    def col_rpm(self, all_engines = False):
        if not all_engines:
            return 'E1 RPM'
        rpm_re = re.compile(r'E\d RPM')
        return [name for name in self.column_idx.keys() if rpm_re.match(name)]

    def createTimestampColumnReader(self):
        date_col = self.column_idx.get('Lcl Date', -1)
        if date_col == -1:
            raise FlightLogException('Garmin log missing "Lcl Date" column')
        time_col = self.column_idx.get('Lcl Time', -1)
        if time_col == -1:
            raise FlightLogException('Garmin log missing "Lcl Time" column')
        return GarminTimestampReader(date_col, time_col)

    def createElapsedColumnReader(self):
        date_col = self.column_idx.get('Lcl Date', -1)
        if date_col == -1:
            raise FlightLogException('Garmin log missing "Lcl Date" column')
        time_col = self.column_idx.get('Lcl Time', -1)
        if time_col == -1:
            raise FlightLogException('Garmin log missing "Lcl Time" column')
        return GarminElapsedReader(self.start_time, date_col, time_col)

    
def process_file(filename):
    log = FlightLog.open(filename)
    # print('columns: ' + repr(log.columns))
    # print('column_idx: ' + repr(log.column_idx))
    # print(log.col_latitude())
    # print(log.col_longitude())
    # print(log.col_CHT())
    # print(log.start_time)


    column_names = [COLUMN_NAME_ELAPSED,
                    log.col_rpm(),
                    *log.col_CHT()]
    print('  '.join(column_names))
    result = log.read(column_names)
    n_cols = len(result)
    n_rows = len(result[0])
    for r in range(n_rows):
        for c in range(n_cols):
            sys.stdout.write(str(result[c][r]) + '  ')
        sys.stdout.write('\n')

    
    # print('longitudes: ' + repr(result[1]))
    # print('latitudes: ' + repr(result[0]))
    

def main(args):
    for filename in args:
        print(filename)
        try:
            process_file(filename)
        except FlightLogException as e:
            print(f'Error reading {filename}: ' + str(e))
    

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
    
