#!/usr/bin/env python3

"""
Look for Garmin files where UTCOfst changes.
"""

import sys
import flight_log

def read_log(filename):
    log = flight_log.FlightLog.open(filename)
    if log.vendor() != flight_log.VENDOR_GARMIN:
        return
    
    [tz_offset_col] = log.read(['UTCOfst'])
    prev_value = None
    values_seen = []
    for value in tz_offset_col:
        if value and value != prev_value:
            if not prev_value or not prev_value.startswith(value):
                prev_value = value
                values_seen.append(value)


    if len(values_seen) > 1:
        print(f'{filename}\t{" ".join(values_seen)}')
        
    elif len(values_seen) == 1:
        print(f'{filename}: {values_seen[0]}')
    # else:
    #     print(f'{filename}: None')

    
def main(args):

    input_list = flight_log.expand_directories(args)
    n_files = len(input_list)
                  
    for i, filename in enumerate(input_list):
        try:
            read_log(filename)
            # if n_files > 1:
            #     sys.stdout.write(f'\r{i+1} of {n_files} logs read')
        except flight_log.FlightLogException as e:
            pass
        except Exception as e2:
            print(f'Exception reading {filename}: {e2}')

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
