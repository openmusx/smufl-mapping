cmake_minimum_required(VERSION 3.14)

include(FetchContent)

FetchContent_Declare(
	googletest
    URL https://github.com/google/googletest/releases/download/v1.15.2/googletest-1.15.2.tar.gz
	DOWNLOAD_EXTRACT_TIMESTAMP TRUE
)
# For Windows: Prevent overriding the parent project's compiler/linker settings
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

enable_testing()

add_executable(smufl_mapping_tests
    legacy_mapping_tests.cpp
    smufl_mapping_tests.cpp
)

set(CMAKE_WARN_DEPRECATED ON CACHE BOOL "Suppress deprecation warnings for external projects" FORCE)
if (CMAKE_CXX_COMPILER_ID MATCHES "AppleClang|Clang|GNU")
    # Extra warnings for Clang/AppleClang
    target_compile_options(smufl_mapping_tests PRIVATE -Wall -Wextra -Werror -Wpedantic)
elseif (CMAKE_CXX_COMPILER_ID MATCHES "MSVC")
    # Extra warnings for MSVC
    target_compile_options(smufl_mapping_tests PRIVATE /Zc:__cplusplus /W4 /WX)
endif()

target_link_libraries(smufl_mapping_tests PRIVATE
    smufl_mapping
    gtest_main
)

target_include_directories(smufl_mapping_tests
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../src
)

include(GoogleTest)
gtest_discover_tests(smufl_mapping_tests)

function(add_python_legacy_test test_name script)
    add_test(
        NAME ${test_name}
        COMMAND Python3::Interpreter ${CMAKE_CURRENT_SOURCE_DIR}/${script}
    )
endfunction()

if(TARGET Python3::Interpreter)
    add_python_legacy_test(
        legacy_duplicate_codepoints_overwrite
        duplicate_legacy_codepoints_test.py
    )
    add_python_legacy_test(
        legacy_duplicate_legacycodepoints_across_entries
        duplicate_legacy_entry_codepoints_test.py
    )
    add_python_legacy_test(
        legacy_duplicate_legacycodepoints_in_array
        duplicate_legacy_array_codepoints_test.py
    )
    add_python_legacy_test(
        legacy_font_metadata
        legacy_font_metadata_test.py
    )
    add_python_legacy_test(
        legacy_unresolved_codepoint_is_nullopt
        legacy_unresolved_codepoint_test.py
    )
else()
    message(STATUS "Skipping Python legacy tests: Python3::Interpreter not available.")
endif()
