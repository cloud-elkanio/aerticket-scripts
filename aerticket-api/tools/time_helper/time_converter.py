import time
import datetime



def epoch_time_now():
    """ gives a current epoch time """
    epoch_time = time.time()
    epoch_time_int = int(epoch_time)
    return  epoch_time_int



def to_date_time(epoch_time_int, stringify=None):
    """ convert epoch time to date time objects if stringify=True then it will return date time in string"""
    time_struct = time.localtime(epoch_time_int)
    date_time = datetime.datetime.fromtimestamp(epoch_time_int)
    if stringify:
        return date_time.strftime("%Y-%m-%d %H:%M:%S")
    else:
        return date_time



