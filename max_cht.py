#!/usr/bin/env python3

"""
Outputs the max CHT found in each input file.

"""

from flight_log import FlightLog
from flight_log import FlightLogException
import sys


def temperatureSlot(temp):
    """
    Round temperature down to the nearest multiple of 10, with a floor of 0.
    """
    if temp < 0:
        return 0
    return int(temp / 10) * 10


def log_max_cht(filename):
    log = FlightLog.open(filename)
    cht_col_names = log.col_CHT()

    # if the log is from a jet, there are no CHT columns, so skip the file
    if not cht_col_names:
        return
    
    column_names = ['elapsed',
                    *cht_col_names]
    data = log.read(column_names)

    max_cht = 0
    for i, column in enumerate(data[1:]):
        col_max = max(column)
        max_cht = max(max_cht, col_max)

    print(f'{max_cht}\t{filename}')
    


def main(args):
    
    for i, filename in enumerate(args):
        try:
            log_max_cht(filename)
        except FlightLogException as e:
            # sys.stderr.write(f'\nError reading {filename}: ' + str(e) + '\n')
            pass

    if len(args) > 1:
        sys.stdout.write('\n')
            

    

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
