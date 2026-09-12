cmake_minimum_required(VERSION 3.14)
project(smufl_mapping LANGUAGES CXX)

# C++ settings
if(NOT CMAKE_CXX_STANDARD)
    set(CMAKE_CXX_STANDARD 23)
endif()

# Enforce at least C++17, allow higher if set by the parent
if(CMAKE_CXX_STANDARD LESS 17)
    message(FATAL_ERROR "Smufl_mapping requires at least C++17. Current: C++${CMAKE_CXX_STANDARD}")
endif()

set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

message(STATUS "Smufl_mapping C++ standard: ${CMAKE_CXX_STANDARD}")

option(SMUFL_MAPPING_USE_PREGENERATED_HEADERS "Use checked-in generated headers (no Python, no FetchContent)" ON)

if(NOT SMUFL_MAPPING_USE_PREGENERATED_HEADERS)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
endif()

include(FetchContent)

if(NOT SMUFL_MAPPING_USE_PREGENERATED_HEADERS)
    # Fetch SMuFL spec
    FetchContent_Declare(
        smufl_w3c
        GIT_REPOSITORY https://github.com/w3c-cg/smufl.git
        GIT_TAG 753f551ca6f96bf24ba38aa2d8a317e706238c51
        SOURCE_SUBDIR _cmake_disabled_please_ignore # this is a hack to prevent FetchContent_Declare from running the fetched content cmake.
        # see https://stackoverflow.com/questions/79261625/cmake-fetchcontent-with-header-only-project/79261858#79261858
    )
    FetchContent_MakeAvailable(smufl_w3c)
    message(STATUS "smufl_w3c fetched at: ${smufl_w3c_SOURCE_DIR}")

    # Generate auto headers
    include(cmake/GenerateSmuflMaps.cmake)
    generate_smuflmap_headers()
    add_custom_target(generate_smuflmaps DEPENDS ${SMUFL_MAPPING_GENERATED_HEADERS})
    include(cmake/GenerateLegacyMaps.cmake)
    generate_legacy_fontmap_headers()
    add_custom_target(generate_legacy_maps DEPENDS ${GENERATED_LEGACY_HEADERS})
else()
    set(SMUFL_MAPPING_GENERATED_HEADERS
        "${CMAKE_CURRENT_SOURCE_DIR}/src/detail/glyphnames_smufl.h"
        "${CMAKE_CURRENT_SOURCE_DIR}/src/detail/glyphnames_finale.h"
        "${CMAKE_CURRENT_SOURCE_DIR}/src/detail/glyphnames_bravura.h"
    )
    file(GLOB GENERATED_LEGACY_HEADERS "${CMAKE_CURRENT_SOURCE_DIR}/src/detail/legacy/*.h")
    list(APPEND GENERATED_LEGACY_HEADERS "${CMAKE_CURRENT_SOURCE_DIR}/src/detail/glyphnames_legacy.h")
    message(STATUS "Using checked-in generated headers (no Python, no FetchContent).")
endif()

# Library target
add_library(smufl_mapping STATIC
    src/smufl_mapping.cpp
    src/smufl_mapping.h
    ${SMUFL_MAPPING_GENERATED_HEADERS}
    ${GENERATED_LEGACY_HEADERS}
)

if(NOT SMUFL_MAPPING_USE_PREGENERATED_HEADERS)
    add_dependencies(smufl_mapping
        generate_smuflmaps
        generate_legacy_maps
    )
endif()

# Public headers are in src/
target_include_directories(smufl_mapping
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/src>
        $<INSTALL_INTERFACE:include>
)

# Compiler warnings (optional)
target_compile_features(smufl_mapping PUBLIC cxx_std_17)
target_compile_options(smufl_mapping PRIVATE
    $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall -Wextra -pedantic>
    $<$<CXX_COMPILER_ID:MSVC>:/W4>
)

# === Testing ===
option(smufl_mapping_BUILD_TESTING "Build smufl_mapping unit tests" ON)

include(CTest)  # sets BUILD_TESTING
if(smufl_mapping_BUILD_TESTING)
    message(STATUS "Testing enabled for smufl_mapping_BUILD_TESTING.")
    enable_testing()
    add_subdirectory(tests)
else()
    message(STATUS "Testing not enabled for smufl_mapping_BUILD_TESTING.")
endif()
