#!/usr/bin/env python3

import sys

import flight_log


def main(args):

    input_list = flight_log.expand_directories(args)
    for filename in input_list:
        try:
            read_log(filename, temp_slots)
            if len(args) > 1:
                sys.stdout.write(f'\r{i+1} of {len(args)} logs read')
        except FlightLogException as e:
            sys.stderr.write(f'\nError reading {filename}: ' + str(e) + '\n')

    

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
