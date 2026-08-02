#!/usr/bin/env python3

"""
Read flight logs and list ones where any CHT reached 410 or higher.

from my logs:
46    2015-03-30 13:15:51 ./log_150330_125558_KVGT.csv
67    2015-04-26 11:28:06 ./log_150426_111915_KNUQ.csv
381   2019-10-09 15:57:07 ./log_191009_153437_KPIA.csv
545   2019-10-16 18:35:43 ./log_191016_164052_KCMI.csv
128   2019-10-20 15:50:39 ./log_191020_144440_KNEW.csv
66    2021-07-28 11:05:45 ./log_210728_104524_KCMI.csv


from the plane Chad is looking at in Wisconsin:
41    2018-05-22 00:29:50 ./log_180521_233126_KOMA.csv
98    2018-05-30 10:20:02 ./log_180530_100033_KNUQ.csv
204   2018-10-18 11:15:50 ./log_181018_091525_KSDL.csv
77    2019-08-09 10:31:08 ./log_190809_094302_KLUK.csv
231   2020-03-17 07:51:31 ./log_200317_073950_KFHB.csv
139   2020-07-15 18:19:26 ./log_200715_172925_KLUK.csv
135   2020-09-04 11:42:22 ./log_200904_113131_KGMU.csv
10    2021-07-29 09:45:28 ./log_210729_091833_KLUK.csv
122   2021-09-19 14:53:52 ./log_210919_141720_KTYS.csv
1130  2021-12-15 14:15:56 ./log_211215_135433_KLUK.csv
5     2022-06-17 11:56:10 ./log_220617_102550_KEQY.csv
72    2022-08-27 00:01:25 ./log_220826_234002_KEQY.csv
216   2022-09-23 21:23:19 ./log_220923_205102_KUZA.csv
75    2024-06-24 13:18:12 ./log_240624_122803_KRMG.csv
3     2024-06-26 12:58:46 ./log_240626_105814_KTYS.csv
386   2024-08-08 13:57:43 ./log_240808_133032_KJBR.csv

"""

from flight_log import FlightLog
from flight_log import FlightLogException
from flight_log import expand_directories
import sys


HIGH_CHT_VALUE = 410


def temperatureSlot(temp):
    """
    Round temperature down to the nearest multiple of 10, with a floor of 0.
    """
    if temp < 0:
        return 0
    return int(temp / 10) * 10


def count_high_temps(data):
    pass


def read_log(filename):
    log = FlightLog.open(filename)
    cht_col_names = log.col_cht()

    # if the log is from a jet, there are no CHT columns, so skip the file
    if not cht_col_names:
        return
    
    column_names = ['timestamp'] + cht_col_names
    data = log.read(column_names)
    n_rows = len(data[0])
    n_cols = len(column_names)
    n_high_cht_rows = 0
    first_hot_time = None

    for col in data[1:]:
        for i, cht in enumerate(col):
            if cht == None:
                continue
            
            if cht >= HIGH_CHT_VALUE:
                if first_hot_time == None:
                    first_hot_time = data[0][i]
                n_high_cht_rows += 1

    if n_high_cht_rows > 0:
        print(f'{n_high_cht_rows:<5} {first_hot_time} {filename}')


def main(args):
    input_list = expand_directories(args)

    print('count filename')
                  
    for i, filename in enumerate(input_list):
        try:
            read_log(filename)
            # if n_files > 1:
            #     sys.stdout.write(f'\r{i+1} of {n_files} logs read')
        except FlightLogException as e:
            # sys.stderr.write(f'Error reading {filename}: ' + str(e) + '\n')
            pass
    

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
