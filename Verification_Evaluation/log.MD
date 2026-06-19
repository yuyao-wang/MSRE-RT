## 00 - converge to zero (14 at 2000 steps)
```python
# Neutronics
dt=0.2 # fixed time step
L = 172  # Length of the spatial domain, m
# L = 22.9
N = 200  # Number of spatial points
dz = L / (N - 1)    # Spatial step size
# V = 4e5
V = 1.103497 * 1e8  # cm/s           
# D = 0.390016 * 8   
D = 0.96343 * 7  # cm      
# sigma_a =0.0835   
sigma_a=1.58430*1e-2/8 # cm^-1        
nu_sigma_f = 3.33029e-2/8 # cm^-1
# nu_sigma_f = 3.33029
# sigma_f= nu_sigma_f/2.41   
beta = [0.000228, 0.000788, 0.000664, 0.000736, 0.000136, 0.000088] # Delayed neutron fractions
Beta = sum(beta)      # 0.00264
```
## 01 - converge to zero (0.04 at 1500 steps)
```python
# Neutronics
dt=0.2 # fixed time step
L = 172  # Length of the spatial domain, m
# L = 22.9
N = 200  # Number of spatial points
dz = L / (N - 1)    # Spatial step size
# V = 4e5
V = 1.103497 * 1e8  # cm/s           
# D = 0.390016 * 8   
D = 0.96343 * 8  # cm      
# sigma_a =0.0835   
sigma_a=1.58430*1e-2/8 # cm^-1        
nu_sigma_f = 3.33029e-2/8 # cm^-1
# nu_sigma_f = 3.33029
# sigma_f= nu_sigma_f/2.41   
beta = [0.000228, 0.000788, 0.000664, 0.000736, 0.000136, 0.000088] # Delayed neutron fractions
Beta = sum(beta)      # 0.00264
# Beta = 0.0045
delta=Beta*nu_sigma_f
# beta2 = [0.000228, 0.000788, 0.000664, 0.000736, 0.000136, 0.000088]
lambda_i = [0.0126, 0.0337, 0.139, 0.325, 1.13, 2.5]    # Decay constants
# sum(lambda_i) = 4.1403        # 0.08
# initial condition
phi_0= 5226.54 * np.ones(N); #5226.54
c0 = (delta / sum(lambda_i)) * phi_0
```
## 02 - explode
```python
# Neutronics
dt=0.2 # fixed time step
L = 172  # Length of the spatial domain, m
# L = 22.9
N = 200  # Number of spatial points
dz = L / (N - 1)    # Spatial step size
# V = 4e5
V = 1.103497 * 1e8  # cm/s           
# D = 0.390016 * 8   
D = 0.96343 * 7  # cm      
# sigma_a =0.0835   
sigma_a=1.58430*1e-2/7 # cm^-1        
nu_sigma_f = 3.33029e-2/7 # cm^-1
# nu_sigma_f = 3.33029
# sigma_f= nu_sigma_f/2.41   
beta = [0.000228, 0.000788, 0.000664, 0.000736, 0.000136, 0.000088] # Delayed neutron fractions
Beta = sum(beta)      # 0.00264
# Beta = 0.0045
delta=Beta*nu_sigma_f
# beta2 = [0.000228, 0.000788, 0.000664, 0.000736, 0.000136, 0.000088]
lambda_i = [0.0126, 0.0337, 0.139, 0.325, 1.13, 2.5]    # Decay constants
# sum(lambda_i) = 4.1403        # 0.08
# initial condition
phi_0= 5226.54 * np.ones(N); #5226.54
```
## 03 - explode
```python
# Neutronics
dt=0.2 # fixed time step
L = 172  # Length of the spatial domain, m
# L = 22.9
N = 200  # Number of spatial points
dz = L / (N - 1)    # Spatial step size
# V = 4e5
V = 1.103497 * 1e7  # cm/s           
# D = 0.390016 * 8   
D = 0.96343 * 7  # cm      
# sigma_a =0.0835   
sigma_a=1.58430*1e-2/7 # cm^-1        
nu_sigma_f = 3.33029e-2/7 # cm^-1
```
## 04 - explode and stuck (in solver loop)
```python
# Neutronics
dt=0.2 # fixed time step
L = 172  # Length of the spatial domain, m
# L = 22.9
N = 200  # Number of spatial points
dz = L / (N - 1)    # Spatial step size
# V = 4e5
V = 1.103497 * 1e7 * 8  # cm/s           
# D = 0.390016 * 8   
D = 0.96343 * 7  # cm      
# sigma_a =0.0835   
sigma_a=1.58430*1e-2/7 # cm^-1        
nu_sigma_f = 3.33029e-2/7 # cm^-1
```
## 05 - explode
```python
V = 1.103497 * 1e7  # cm/s           
# D = 0.390016 * 8   
D = 0.96343 * 7  # cm      
# sigma_a =0.0835   
sigma_a=1.58430*1e-2/8 # cm^-1        
nu_sigma_f = 3.33029e-2/7 # cm^-1
```
## 06 - converge to 0 (0.004 at 1000)
```python
# Neutronics
dt=0.2 # fixed time step
L = 172  # Length of the spatial domain, m
# L = 22.9
N = 200  # Number of spatial points
dz = L / (N - 1)    # Spatial step size
# V = 4e5
V = 1.103497 * 1e7  # cm/s           
# D = 0.390016 * 8   
D = 0.96343 * 7  # cm      
# sigma_a =0.0835   
sigma_a=1.58430*1e-2/7.5 # cm^-1        
nu_sigma_f = 3.33029e-2/8 # cm^-1
beta = [0.000228, 0.000788, 0.000664, 0.000736, 0.000136, 0.000088] # Delayed neutron fractions
Beta = sum(beta)      # 0.00264
# Beta = 0.0045
delta=Beta*nu_sigma_f
# beta2 = [0.000228, 0.000788, 0.000664, 0.000736, 0.000136, 0.000088]
lambda_i = [0.0126, 0.0337, 0.139, 0.325, 1.13, 2.5]    # Decay constants
# sum(lambda_i) = 4.1403        # 0.08
# initial condition
phi_0= 5226.54 * 1e-2 * np.ones(N); #5226.54
c0 = (delta / sum(lambda_i)) * phi_0
```