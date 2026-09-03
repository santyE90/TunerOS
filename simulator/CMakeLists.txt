add_library(tuneros_simulator STATIC
    src/contracts.cpp
    src/drivetrain.cpp
    src/faults.cpp
    src/initial_conditions.cpp
    src/scenario.cpp
    src/simulation.cpp
    src/simulation_clock.cpp
    src/vehicle_profiles.cpp
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

    add_executable(tuneros_contract_tests
        tests/contracts_test.cpp
    )
    target_link_libraries(tuneros_contract_tests PRIVATE TunerOS::Simulator)
    target_compile_features(tuneros_contract_tests PRIVATE cxx_std_20)

    if(MSVC)
        target_compile_options(tuneros_contract_tests PRIVATE /W4 /permissive-)
    else()
        target_compile_options(tuneros_contract_tests PRIVATE -Wall -Wextra -Wpedantic)
    endif()

    add_test(NAME simulator.contracts COMMAND tuneros_contract_tests)

    add_executable(tuneros_simulation_tests
        tests/simulation_test.cpp
    )
    target_link_libraries(tuneros_simulation_tests PRIVATE TunerOS::Simulator)
    target_compile_features(tuneros_simulation_tests PRIVATE cxx_std_20)

    if(MSVC)
        target_compile_options(tuneros_simulation_tests PRIVATE /W4 /permissive-)
    else()
        target_compile_options(tuneros_simulation_tests PRIVATE -Wall -Wextra -Wpedantic)
    endif()

    add_test(NAME simulator.simulation COMMAND tuneros_simulation_tests)

    add_executable(tuneros_phase1b_tests
        tests/phase1b_test.cpp
    )
    target_link_libraries(tuneros_phase1b_tests PRIVATE TunerOS::Simulator)
    target_compile_features(tuneros_phase1b_tests PRIVATE cxx_std_20)

    if(MSVC)
        target_compile_options(tuneros_phase1b_tests PRIVATE /W4 /permissive-)
    else()
        target_compile_options(tuneros_phase1b_tests PRIVATE -Wall -Wextra -Wpedantic)
    endif()

    add_test(NAME simulator.phase1b COMMAND tuneros_phase1b_tests)

    add_executable(tuneros_city_tests
        tests/city_test.cpp
    )
    target_link_libraries(tuneros_city_tests PRIVATE TunerOS::Simulator)
    target_compile_features(tuneros_city_tests PRIVATE cxx_std_20)

    if(MSVC)
        target_compile_options(tuneros_city_tests PRIVATE /W4 /permissive-)
    else()
        target_compile_options(tuneros_city_tests PRIVATE -Wall -Wextra -Wpedantic)
    endif()

    add_test(NAME simulator.city COMMAND tuneros_city_tests)

    add_executable(tuneros_fault_tests
        tests/faults_test.cpp
    )
    target_link_libraries(tuneros_fault_tests PRIVATE TunerOS::Simulator)
    target_compile_features(tuneros_fault_tests PRIVATE cxx_std_20)

    if(MSVC)
        target_compile_options(tuneros_fault_tests PRIVATE /W4 /permissive-)
    else()
        target_compile_options(tuneros_fault_tests PRIVATE -Wall -Wextra -Wpedantic)
    endif()

    add_test(NAME simulator.faults COMMAND tuneros_fault_tests)
endif()
