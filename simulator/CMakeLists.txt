add_library(tuneros_simulator STATIC
    src/version.cpp
)

add_library(TunerOS::Simulator ALIAS tuneros_simulator)

target_compile_features(tuneros_simulator PUBLIC cxx_std_20)
target_include_directories(tuneros_simulator
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
)

if(MSVC)
    target_compile_options(tuneros_simulator PRIVATE /W4 /permissive-)
else()
    target_compile_options(tuneros_simulator PRIVATE -Wall -Wextra -Wpedantic)
endif()

if(BUILD_TESTING)
    add_executable(tuneros_simulator_tests
        tests/version_test.cpp
    )
    target_link_libraries(tuneros_simulator_tests PRIVATE TunerOS::Simulator)
    target_compile_features(tuneros_simulator_tests PRIVATE cxx_std_20)

    if(MSVC)
        target_compile_options(tuneros_simulator_tests PRIVATE /W4 /permissive-)
    else()
        target_compile_options(tuneros_simulator_tests PRIVATE -Wall -Wextra -Wpedantic)
    endif()

    add_test(NAME simulator.version COMMAND tuneros_simulator_tests)
endif()

