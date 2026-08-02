#!/usr/bin/env python3

from flight_log import *
from datetime import datetime
from datetime import time


def timesec(t):
    """
    Given a datetime.time object, returns the time in seconds since midnight.
    """
    return t.second + 60 * (t.minute + 60 * t.hour)


def mdyhms_to_datetime(s):
    fields = parse_int_tuple(s)
    if len(fields) != 6:
        return None
    month, day, year, hour, minute, second = fields
    if year > 70:
        year += 1900
    else:
        year += 2000
    return datetime(year, month, day, hour, minute, second)


def read_log(filename, one_line_jumpers):
    log = FlightLog.open(filename)
    if log.vendor() != VENDOR_AVIDYNE:
        return

    with open(filename) as inf:
        inf.readline()
        header_timestamp = inf.readline().strip()
    if not header_timestamp:
        return

    header_datetime = mdyhms_to_datetime(header_timestamp)
    if not header_datetime:
        return
    header_time = time(header_datetime.hour, header_datetime.minute,
                       header_datetime.second)

    times, lats, lons = log.read(['TIME', 'LAT', 'LON'])
    n = len(times)
    assert(len(lats)==n and len(lons)==n)
    if n <= 1: return


    # expect first timestamp to be the header time rounded down to a multiple
    # of 6 seconds
    first_time = time.fromisoformat(times[0])
    first_diff = timesec(header_time) - timesec(first_time)
    if first_diff < -1 or first_diff >= 6:
        if n == 1:
            print(f'single line jumper: {header_timestamp} -> {times[0]}  {filename}')
            one_line_jumpers.append(filename)
            return
        print(filename)
        print(f'  first diff is {first_diff} seconds ({header_timestamp} - {times[0]})')
        print(f'  file contains {n} data rows')
        
    # i = 0
    # while i < n:
    #     i += 1
    


def main(args):
    one_line_jumpers = []
    for i, filename in enumerate(args):
        try:
            read_log(filename, one_line_jumpers)
        except FlightLogException as e:
            if e != 'File is empty':
                continue
            print(f'Error reading {filename}: ' + str(e))

    print(f'{len(one_line_jumpers)} file have timestamp jumps but only one data line')
    
    

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))


