#!/usr/bin/env python3

"""
Extract just time (UTC absolute and relative) and position from one log.
"""

import sys
import flight_log


def main(args):

    if len(args) != 1:
        print('\n  time_and_position.py <logfile>\n')
        return
    
    log = flight_log.FlightLog.open(args[0])
    cols = log.read(['timestamp', 'elapsed', log.col_latitude(),
                     log.col_longitude()])
    print('time\telapsed\tlat\tlon')
    n_rows = len(cols[0])
    for i in range(n_rows):
        timestamp = cols[0][i]
        if timestamp:
            timestamp = timestamp.strftime("%Y-%m-%d:%H:%M:%S")
        else:
            timestamp = ''
            
        elapsed = cols[1][i]
        if elapsed == None:
            elapsed = ''
            
        lat = cols[2][i]
        if lat:
            lat = f'{lat:.4f}'
        else:
            lat = ''
            
        lon = cols[3][i]
        if lat:
            lon = f'{lon:.4f}'
        else:
            lon = ''
            
        print(f'{timestamp}\t{elapsed}\t{lat}\t{lon}')


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
