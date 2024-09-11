from parameters import *
import numpy as np

def transport_delay(T0, time_delay, initial_output, buffer, step):
        
    # print("size of buffer" + str(len(buffer)))
    if time_delay == 0:
        return T0
    
    if step < time_delay:
        T1=initial_output
        buffer.append(T0)
        
    else:
        T1=buffer.pop(0)
        buffer.append(T0)
        
    return T1