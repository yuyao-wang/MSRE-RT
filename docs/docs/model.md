# Model Overview

MSRE-RT models a reduced one-dimensional flowing-fuel molten-salt reactor
system. The code is organized around a coupled reactor-core and
balance-of-plant workflow rather than a standalone neutronics calculation.

## Physical Blocks

- Reactor core: axial flux, precursor groups, reactivity feedback, fuel
  temperature, and graphite temperature.
- Delayed-neutron transport: precursor advection and recirculation through
  modeled loop delays.
- Heat exchangers: HX1 and HX2 hot/cold-side temperature evolution.
- Power conversion proxy: a simplified downstream balance-of-plant temperature
  update used for closed-loop transient studies.

## Split Boundary

The hardware-oriented split is made at modeled transport-delay boundaries. The
host runtime maintains delayed channels and supplies committed inlet values to
the core and BOP kernels. This preserves the same numerical staging used by the
Python and plain C++ references while allowing the hardware kernels to be
launched independently.

## Scope

The repository is intended for numerical verification and hardware-emulation
research. It is not a licensed or safety-certified reactor analysis package.
