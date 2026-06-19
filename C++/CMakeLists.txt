cmake_minimum_required(VERSION 3.20)

project(msr_plain_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(msr_plain msr_plain.cpp)
