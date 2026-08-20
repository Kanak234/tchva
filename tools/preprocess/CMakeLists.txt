cmake_minimum_required(VERSION 3.20)
project(fk_preprocess CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_compile_options(-O2 -Wall -Wextra -Wpedantic)

add_executable(fk-preprocess main.cpp)

target_compile_features(fk-preprocess PRIVATE cxx_std_20)
