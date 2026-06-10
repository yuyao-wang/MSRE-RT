def transport_delay(T0, time_delay, initial_output, buffer, step):
        
    # print("size of buffer" + str(len(buffer)))
    
    if step < time_delay:
        T1 = initial_output
        buffer.append(T0)
    else:
        if hasattr(buffer, "popleft"):
            T1 = buffer.popleft()
        else:
            T1 = buffer.pop(0)
        buffer.append(T0)
        
    return T1
