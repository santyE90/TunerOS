add_library(tuneros_can STATIC
    src/in_memory_transport.cpp
)
add_library(TunerOS::Can ALIAS tuneros_can)

target_compile_features(tuneros_can PUBLIC cxx_std_20)
target_include_directories(tuneros_can
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
)

add_library(tuneros_dme STATIC
    src/dme_frames.cpp
    src/simulated_dme.cpp
    src/vehicle_network_simulation.cpp
)
add_library(TunerOS::Dme ALIAS tuneros_dme)

target_compile_features(tuneros_dme PUBLIC cxx_std_20)
target_include_directories(tuneros_dme
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
)
target_link_libraries(tuneros_dme PUBLIC TunerOS::Can TunerOS::Simulator)

foreach(target tuneros_can tuneros_dme)
    if(MSVC)
        target_compile_options(${target} PRIVATE /W4 /permissive-)
    else()
        target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic)
    endif()
endforeach()

if(BUILD_TESTING)
    add_executable(tuneros_can_tests tests/can_test.cpp)
    target_link_libraries(tuneros_can_tests PRIVATE TunerOS::Can)

    add_executable(tuneros_dme_frame_tests tests/dme_frames_test.cpp)
    target_link_libraries(tuneros_dme_frame_tests PRIVATE TunerOS::Dme)

    add_executable(tuneros_vehicle_network_tests tests/vehicle_network_test.cpp)
    target_link_libraries(tuneros_vehicle_network_tests PRIVATE TunerOS::Dme)

    foreach(target tuneros_can_tests tuneros_dme_frame_tests tuneros_vehicle_network_tests)
        target_compile_features(${target} PRIVATE cxx_std_20)
        if(MSVC)
            target_compile_options(${target} PRIVATE /W4 /permissive-)
        else()
            target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic)
        endif()
    endforeach()

    add_test(NAME can.contracts_transport COMMAND tuneros_can_tests)
    add_test(NAME can.dme_frames COMMAND tuneros_dme_frame_tests)
    add_test(NAME can.vehicle_network COMMAND tuneros_vehicle_network_tests)
endif()
