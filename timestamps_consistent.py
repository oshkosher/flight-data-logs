#!/usr/bin/env python3

"""
Scan logs to see if my assumptions about the consistency of their
timestamps are correct.

Assumptions:
 - In Garmin files:
   - The date, time, and UTCOfst fields may start blank, then once any one
     of them is non-blank all will be non-blank and contain valid values.

     counter-examples:
     N63EK  log_150326_111558_KRYV.csv
     first line is valid, then 4 blank, then good

     N63EK  log_150326_093129______.csv
     first 2 lines are valid, then 2 blank, then good

   - The UTCOfst field may change (a change initiated by the user, not an
     automatic switch) and this will trigger a jump in the date/time, but
     the UTC time (date/time - UTCOfst) will not jump more than a few seconds.

     counterexamples
     N63EK  log_170717_195245_KDWA.csv
       line 833 is 2017-07-17, 20:00:33
       line 834 is 2017-07-17, 20:00:20, a jump of -13 seconds, 13 minutes
       into the log


   - If 'Lcl Date', 'Lcl Time', and 'UTCOfst' fields are concatenated
     and the result is non-blank, then the result will be successfully
     parsed with datetime.strptime(s, '%Y-%m-%d %H:%M:%S %z')
   - The jump between adjacent UTC time values will usually be 1 second,
     but will occasionally be up to +-20 seconds.
 - In Avidyne files:
   - the time may jump once, but only at the beginning
     of the file, before the latitude&longitude are valid
 - once valid coordinates are listed, every later row will have valid
   coordinates.
   exception: samples/garmin-sr22t-log_161119_154619_KEYW.csv
 - the 'elapsed' column is always >= 0 and never goes down
 - the 'timestamp' column is always >= log.start_time and never goes down
"""

import sys, re, time, calendar
import flight_log
from datetime import timedelta, datetime, timezone
# from flight_log import FlightLog, FlightLogException

IGNORE_FORMAT_ERRORS = True

YMD_RE = re.compile(r'(\d\d\d\d)-(\d\d)-(\d\d)')
HMS_RE = re.compile(r'(\d\d):(\d\d):(\d\d)')
UTC_OFFSET_RE = re.compile(r' *([-+])(\d\d):(\d\d)')
DEGREES_RE = re.compile(r'([-+]?\d+.\d+)')
DATE_TIME_FMT = '%Y-%m-%d %H:%M:%S'
DATE_TIME_TZ_FMT = '%Y-%m-%d %H:%M:%S %z'
GARMIN_MIN_TIME_JUMP = 0
GARMIN_MAX_TIME_JUMP = 10

MIN_TIME = datetime(1990, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
MAX_TIME = datetime(2100, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

garmin_max_time_gap = 0
garmin_time_gaps = {}

def read_log_garmin(log):
    """
    Sample of time gaps:  (seconds, frequency)
    
    -21599: 1
    -17999: 1
    -10799: 1
     -7199: 3
     -3599: 15
       -20: 1
       -13: 2
        -8: 1
        -6: 2
        -5: 2
        -4: 1
        -3: 4
        -2: 2
        -1: 9
         0: 31780
         1: 5432967
         3: 729
         2: 242487
         4: 165
         5: 56
         6: 35
         7: 14
         8: 8
         9: 6
        10: 3
        11: 4
        13: 2
        15: 1
        16: 2
        19: 2
        20: 1
        94: 1
      3601: 7
      7201: 3
      7202: 1
     10801: 1
     18001: 1

    /cygdrive/c/Ed/Dropbox/Aviation/N63EK/Engine logs/log_150527_172934_KNUQ.csv
      backwards jump 1 second at line 19, before lat/lon are valid
    /cygdrive/c/Ed/Dropbox/Aviation/N63EK/Engine logs/log_150205_121922_KLXN.csv
      backwards jump 3599 seconds, 14:35:16 to 13:35:17, tz -06:00 to -07:00
      and 13:38:27 to 12:38:28, -7 to -8
    """
    global garmin_max_time_gap
    
    # Lcl Date: yyyy-mm-dd
    # Lcl Time: hh:mm:ss
    # UTCOfst: [+-]hh:mm
    # Latitude: [+-]dd.ddddddd
    # Longitude: [+-]dd.ddddddd
    date_col, time_col, utc_offset_col, lat_col, lon_col = \
        log.read(['Lcl Date', 'Lcl Time', 'UTCOfst', 'Latitude', 'Longitude'])

    
    n = len(date_col)
    errors = 0
    first_valid_time_seen = False
    position_initial_invalid = True
    prev_utc_sec = None
    prev_timestamp_str = None
    time_diffs = {}
    
    # save the previous value of UTCOfst to avoid recomputing from_utc_offset
    # every time
    prev_utc_offset = None
    from_utc_offset = None
    
    # print(f'{log.filename} {n=}')
    
    for i in range(n):
        line_no = i+4  # 3 header rows + 1-based line numbers
        
        # print(f'line {line_no} date = {date_col[i]!r} {time_is_valid}')

        date_match = YMD_RE.match(date_col[i])
        time_match = HMS_RE.match(time_col[i])
        utc_offset_match = UTC_OFFSET_RE.match(utc_offset_col[i])

        if date_match and time_match and utc_offset_match:
            time_valid = True
        elif not (date_match or time_match or utc_offset_match):
            time_valid = False
        else:
            print(f'ERROR mixed validity {log.filename}:{line_no} date={date_col[i]}, time={time_col[i]}, utc_offset={utc_offset_col[i]}')
            errors += 1
            continue

        if not time_valid:
            if first_valid_time_seen:
                print(f'ERROR time went invalid {log.filename}:{line_no} date={date_col[i]}, time={time_col[i]}, utc_offset={utc_offset_col[i]}')
                first_valid_time_seen = False
                errors += 1
            continue

        if not first_valid_time_seen:
            first_valid_time_seen = True

        # compute from_utc_offset
        # if utc_offset_col[i] != prev_utc_offset:
        #     prev_utc_offset = utc_offset_col[i]
        #     sign, hours, minutes = utc_offset_match.groups()
        #     sign = -1 if sign == '-' else +1
        #     min_diff = sign * (int(hours) * 60 + int(minutes))
        #     from_utc_offset = timedelta(minutes = min_diff)
                
        
        # if not time_match:
        #     print(f'{log.filename}:{line_no} bad time {time_col[i]!r}')
        #     errors += 1

        timestamp_str = (date_col[i] + ' ' + time_col[i] + ' '
                         + utc_offset_col[i])
        try:
            local_timestamp = datetime.strptime(timestamp_str, DATE_TIME_TZ_FMT)
        except ValueError:
            print(f'ERROR bad datetime {log.filename}:{line_no} {timestamp_str}')
            errors += 1
            continue

        # catch problems like a date of 1970-01-01 or 9999-12-31
        if local_timestamp < MIN_TIME or local_timestamp > MAX_TIME:
            print(f'ERROR bad datetime {log.filename}:{line_no} {timestamp_str} outside expected range (year 1990-2100)')
            errors += 1
            continue
        
        utc_seconds = int(local_timestamp.timestamp())

        if prev_utc_sec != None:
            sec_diff = utc_seconds - prev_utc_sec
            if sec_diff < GARMIN_MIN_TIME_JUMP or sec_diff > GARMIN_MAX_TIME_JUMP:
                print(f'ERROR bad time jump{log.filename}:{line_no} {sec_diff} seconds to {timestamp_str}')
            else:

                # print(f'{prev_timestamp_str} - {timestamp_str}: {sec_diff} seconds')
                prev_timestamp_str = timestamp_str
                
                garmin_max_time_gap = max(garmin_max_time_gap, sec_diff)
                # count = time_diffs.get(sec_diff, 0)
                # time_diffs[sec_diff] = count + 1

                count = garmin_time_gaps.get(sec_diff, 0)
                garmin_time_gaps[sec_diff] = count + 1

        prev_utc_sec = utc_seconds

            
                
            
    # print(f'time_diffs: {time_diffs!r}')
    # print(f'{log.filename} garmin ok')


def read_log_avidyne(log):
    # print(f'{log.filename} ok')
    pass


def read_log(filename):
    log = flight_log.FlightLog.open(filename)
    if log.vendor() == flight_log.VENDOR_GARMIN:
        read_log_garmin(log)
    else:
        read_log_avidyne(log)


def main(args):

    input_list = flight_log.expand_directories(args)
    n_files = len(input_list)
                  
    for i, filename in enumerate(input_list):
        try:
            read_log(filename)
            # if n_files > 1:
            #     sys.stdout.write(f'\r{i+1} of {n_files} logs read')
        except flight_log.FlightLogException as e:
            if not IGNORE_FORMAT_ERRORS:
                sys.stderr.write(f'Error reading {filename}: ' + str(e) + '\n')

    print(f'{garmin_time_gaps=}')
    print(f'{garmin_max_time_gap=}')

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
