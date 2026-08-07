# GenerateLegacyMaps.cmake
#
# This file is safe to use with FetchContent or from top-level CMakeLists

get_filename_component(_gen_script_dir "${CMAKE_CURRENT_LIST_DIR}" ABSOLUTE)
set(SMUFL_MAPPING_ROOT "${_gen_script_dir}/..")

function(generate_legacy_fontmap_headers)
    set(SOURCE_DIR "${SMUFL_MAPPING_ROOT}/source_json/legacy")
    set(FINALE_FILE "${SMUFL_MAPPING_ROOT}/source_json/glyphnamesFinale.json")
    set(VALIDATOR_SCRIPT "${SMUFL_MAPPING_ROOT}/tools/validate_legacy_mappings.py")
    set(DUPLICATE_SCRIPT "${SMUFL_MAPPING_ROOT}/tools/check_duplicate_codepoints.py")
    set(PY_SCRIPT "${SMUFL_MAPPING_ROOT}/tools/generate_legacy_glyphnames_map.py")
    set(OUTPUT_DIR "${SMUFL_MAPPING_ROOT}/src/detail/legacy")

    file(GLOB LEGACY_JSON_FILES "${SOURCE_DIR}/*.json")

    if(NOT DEFINED SMUFL_W3C_SOURCE_DIR)
        if(DEFINED smufl_w3c_SOURCE_DIR)
            set(SMUFL_W3C_SOURCE_DIR "${smufl_w3c_SOURCE_DIR}")
        endif()
    endif()

    if(NOT SMUFL_W3C_SOURCE_DIR)
        message(FATAL_ERROR "SMUFL_W3C_SOURCE_DIR is not set. Fetch w3c/smufl first.")
    endif()

    set(SMUFL_W3C_GLYPHNAMES_JSON "${SMUFL_W3C_SOURCE_DIR}/metadata/glyphnames.json")
    if(NOT EXISTS "${SMUFL_W3C_GLYPHNAMES_JSON}")
        message(FATAL_ERROR "SMUFL glyphnames.json does not exist: ${SMUFL_W3C_GLYPHNAMES_JSON}")
    endif()

    set(SMUFL_FONTS_JSON "${SMUFL_MAPPING_ROOT}/source_json/smufl_fonts.json")
    set(SMUFL_FONTS_SCRIPT "${SMUFL_MAPPING_ROOT}/tools/generate_smufl_fonts_map.py")
    set(SMUFL_FONTS_HEADER "${SMUFL_MAPPING_ROOT}/src/detail/smufl_fonts.h")

    set(LEGACY_VALIDATION_STAMP "${CMAKE_BINARY_DIR}/legacy_mappings_validated.stamp")
    add_custom_command(
        OUTPUT "${LEGACY_VALIDATION_STAMP}"
        COMMAND ${Python3_EXECUTABLE} "${VALIDATOR_SCRIPT}" --legacy-dir "${SOURCE_DIR}" --smufl-registry "${SMUFL_FONTS_JSON}"
        COMMAND ${Python3_EXECUTABLE} "${DUPLICATE_SCRIPT}" --std "${SMUFL_W3C_GLYPHNAMES_JSON}" --finale "${SMUFL_MAPPING_ROOT}/source_json/glyphnamesFinale.json" --bravura "${SMUFL_MAPPING_ROOT}/source_json/glyphnamesBravura.json"
        COMMAND ${CMAKE_COMMAND} -E touch "${LEGACY_VALIDATION_STAMP}"
        DEPENDS
            ${LEGACY_JSON_FILES}
            "${SMUFL_FONTS_JSON}"
            "${VALIDATOR_SCRIPT}"
            "${DUPLICATE_SCRIPT}"
            "${SMUFL_W3C_GLYPHNAMES_JSON}"
            "${SMUFL_MAPPING_ROOT}/source_json/glyphnamesFinale.json"
            "${SMUFL_MAPPING_ROOT}/source_json/glyphnamesBravura.json"
        COMMENT "Validating legacy mapping JSON"
        VERBATIM
    )
    add_custom_target(validate_legacy_json DEPENDS "${LEGACY_VALIDATION_STAMP}")

    # Derive the expected output headers
    set(OUTPUT_HEADERS "")
    foreach(json_file IN LISTS LEGACY_JSON_FILES)
        get_filename_component(stem_raw "${json_file}" NAME_WE)
        string(REPLACE " " "_" stem "${stem_raw}")
        string(TOLOWER "${stem}" stem)
        list(APPEND OUTPUT_HEADERS "${OUTPUT_DIR}/${stem}_legacy_map.h")
    endforeach()

    list(APPEND OUTPUT_HEADERS "${SMUFL_MAPPING_ROOT}/src/detail/glyphnames_legacy.h")

    file(MAKE_DIRECTORY "${OUTPUT_DIR}")

    add_custom_command(
        OUTPUT ${OUTPUT_HEADERS}
        COMMAND ${Python3_EXECUTABLE} "${PY_SCRIPT}" ${LEGACY_JSON_FILES}
        DEPENDS ${LEGACY_JSON_FILES} "${FINALE_FILE}" "${PY_SCRIPT}" "${LEGACY_VALIDATION_STAMP}"
        COMMENT "Generating legacy SMuFL fontmap headers"
        VERBATIM
    )

    add_custom_command(
        OUTPUT "${SMUFL_FONTS_HEADER}"
        COMMAND ${Python3_EXECUTABLE} "${SMUFL_FONTS_SCRIPT}"
        DEPENDS "${SMUFL_FONTS_JSON}" "${SMUFL_FONTS_SCRIPT}" "${LEGACY_VALIDATION_STAMP}"
        COMMENT "Generating SMuFL font registry header"
        VERBATIM
    )
    list(APPEND OUTPUT_HEADERS "${SMUFL_FONTS_HEADER}")

    set(GENERATED_LEGACY_HEADERS ${OUTPUT_HEADERS} PARENT_SCOPE)
endfunction()
