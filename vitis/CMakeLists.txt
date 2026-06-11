cmake_minimum_required(VERSION 3.20)

project(msr_vitis_reference LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(msr_vitis_kernel OBJECT msr_vitis_kernel.cpp)
