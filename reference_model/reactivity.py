from parameters import *
import numpy as np

def reactivity(temperature_fuel_r, temperature_graphite_r, temperature_fuel, temperature_graphite, step, time_span, rho_insertion, params):
    
    beta=params['beta']
    lambda_i=params['lambda_i']
    tau_c=params['tau_c']
    tau_l=params['tau_l']
    alpha_f=params['alpha_f']
    alpha_g=params['alpha_g']
    rho_init=params['rho_init']
    L=params['L']
    N=params['N']
    # initial conditions for TH
    scale=params['scale']
    max_rho_change=params['max_rho_change']
    
    rho_0=sum(beta)
    for i in range(6):
        rho_0=rho_0-beta[i]/(1+(1/(lambda_i[i]*tau_c))*(1-np.exp(-lambda_i[i]*tau_l)))
    # rho_0 = 0.0011211260746046986
    # rho_0 = 0.000009
    # print(f'rho_0{rho_0}')
    rho_0=0*np.ones(N)
    
    # rho_0= - 4 * np.sin(np.pi * (np.linspace(0, L, N) ) / (L*4)+(L/4))
    # print(rho_0)
    
    # SOURCE INSERTION
    # REACTIVITY INSERTION
    # No reactivity insertion
    # simtime = 100
    # reacttime = [0, 2500]
    # Periodic 60 PCM for 50 seconds
    # simtime = 500;
    # periodic = [0, 0; 50, 6e-4; 100, 0; 150, -6e-4; 200, 0; 250, 6e-4; 300, 0; 350, -6e-4; 400, 0]; 
    # reactdata = periodic(:,2);
    # reacttime = periodic(:,1);
    # Step up 60 pcm 
    # simtime = 1000;
    # reactdata = [0 6e-3];
    # reacttime = [0 300];
    # % Step down -60 pcm for 10 sec
    # simtime = 100;
    # reactdata = [0 -6e-4];
    # reacttime = [0 50];
    # % Pulse 600 pcm for 0.1 sec
    # simtime = 30;
    # reactdata = [0 6e-3 0];
    # reacttime = [0 10 10.1];
    # react = timeseries(reactdata,reacttime);
    
    reactdata = [rho_init * 1e-5, rho_insertion * 1e-5]
    if step < time_span/2:
        react = reactdata[0]
    else:
        react = reactdata[1]
        # smoothing_factor = 100
        # react_insertion = reactdata[1] * (1 - np.exp(-step / smoothing_factor))
        # react = react_insertion

        
    # rho_feedback=(temperature_fuel_r-temperature_fuel)*alpha_f+(temperature_graphite_r-temperature_graphite)*alpha_g

    rho_feedback = np.clip((temperature_fuel_r - temperature_fuel) * alpha_f +
                       (temperature_graphite_r - temperature_graphite) * alpha_g,
                       -max_rho_change, max_rho_change)

    # rho_feedback = rho_feedback *0
    rho=rho_0+rho_feedback*scale+react
    
    # rho=rho_init * np.ones(N)
    
    # rho=0 * np.ones(N)
    # rho=-0.369e-4 * np.ones(N)
    # if step<=1:
    #     rho=0.0045/2*step*np.ones(N)
    # else:
    #     rho=0.0045/2*np.ones(N)
    
    return rho