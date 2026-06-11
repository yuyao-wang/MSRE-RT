def transport_delay(T0, time_delay, initial_output, buffer, step, dt=1.0):
    delay_steps = max(int(round(float(time_delay) / max(float(dt), 1.0e-12))), 0)

    if step < delay_steps:
        T1 = initial_output
        buffer.append(T0)
    else:
        if hasattr(buffer, "popleft"):
            T1 = buffer.popleft()
        else:
            T1 = buffer.pop(0)
        buffer.append(T0)

    return T1
