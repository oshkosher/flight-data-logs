#!/usr/bin/env python3

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


def read_log(filename, temp_slots):
    log = FlightLog.open(filename)
    cht_col_names = log.col_CHT()

    # if the log is from a jet, there are no CHT columns, so skip the file
    if not cht_col_names:
        return
    
    column_names = ['elapsed',
                    log.col_rpm(),
                    *cht_col_names]
    data = log.read(column_names)
    n_rows = len(data[0])
    n_cols = len(column_names)

    # map temperature slots (multiples of 10) to the number of
    # cylinder*seconds spent in that slot

    prev_time = 0
    for r in range(n_rows):
        
        # ignore entries when the engine is off (RPM < 500)
        rpm = data[1][r]
        if rpm == None or rpm < 500: continue

        # ignore entries before we know what time it is
        elapsed = data[0][r]
        if elapsed == None: continue
        
        time_slice = elapsed - prev_time
        prev_time = elapsed

        for c in range(2, n_cols):
            cht = data[c][r]
            if cht == None: continue
            slot = temperatureSlot(cht)
            
            temp_slots[slot] = time_slice + temp_slots.get(slot, 0)
            # print(f'{slot} += {time_slice}')
        # print()
        
    
def report(temp_slots):
    """
    By using a hash table to track the temperature slots, there
    may be gaps. For example: {300: x, 310: y, 330: z}
    Find the min and max, and step through the full range, even if
    some slots are empty.
    """
    key_list = list(temp_slots.keys())
    key_list.sort()
    min_slot = key_list[0]
    max_slot = key_list[-1]

    total_time = sum(temp_slots.values())

    print('CHT temp    pct  time (seconds)')
    for slot in range(min_slot, max_slot+10, 10):
        slot_label = f'{slot}-{slot+9}'
        time = temp_slots.get(slot, 0)
        pct = 100.0 * time / total_time
        print(f'{slot_label:>7}  {pct:6.2f}  {time}')
        


def main(args):
    temp_slots = {}

    for filename in args:
        # print(filename)
        try:
            read_log(filename, temp_slots)
        except FlightLogException as e:
            sys.stderr.write(f'Error reading {filename}: ' + str(e) + '\n')

    report(temp_slots)
    

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
