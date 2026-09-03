add_library(tuneros_can STATIC
    src/in_memory_transport.cpp
)
add_library(TunerOS::Can ALIAS tuneros_can)

target_compile_features(tuneros_can PUBLIC cxx_std_20)
target_include_directories(tuneros_can
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
)

add_library(tuneros_can_gateway STATIC
    src/gateway_protocol.cpp
    src/tcp_gateway.cpp
)
add_library(TunerOS::CanGateway ALIAS tuneros_can_gateway)

target_compile_features(tuneros_can_gateway PUBLIC cxx_std_20)
target_include_directories(tuneros_can_gateway
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
)
target_link_libraries(tuneros_can_gateway PUBLIC TunerOS::Can)
if(WIN32)
    target_link_libraries(tuneros_can_gateway PRIVATE ws2_32)
endif()

add_library(tuneros_dme STATIC
    src/dme_frames.cpp
    src/simulated_dme.cpp
)
add_library(TunerOS::Dme ALIAS tuneros_dme)

target_compile_features(tuneros_dme PUBLIC cxx_std_20)
target_include_directories(tuneros_dme
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
)
target_link_libraries(tuneros_dme PUBLIC TunerOS::Can TunerOS::Simulator)

add_library(tuneros_dsc STATIC
    src/dsc_frames.cpp
    src/simulated_dsc.cpp
)
add_library(TunerOS::Dsc ALIAS tuneros_dsc)

target_compile_features(tuneros_dsc PUBLIC cxx_std_20)
target_include_directories(tuneros_dsc
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
)
target_link_libraries(tuneros_dsc PUBLIC TunerOS::Can TunerOS::Simulator)

add_library(tuneros_vehicle_network STATIC
    src/vehicle_network_simulation.cpp
)
add_library(TunerOS::VehicleNetwork ALIAS tuneros_vehicle_network)

target_compile_features(tuneros_vehicle_network PUBLIC cxx_std_20)
target_include_directories(tuneros_vehicle_network
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
)
target_link_libraries(tuneros_vehicle_network
    PUBLIC
        TunerOS::Can
        TunerOS::Dme
        TunerOS::Dsc
        TunerOS::Simulator
)

add_executable(tuneros_gateway_sim src/gateway_sim_main.cpp)
target_compile_features(tuneros_gateway_sim PRIVATE cxx_std_20)
target_link_libraries(tuneros_gateway_sim
    PRIVATE
        TunerOS::CanGateway
        TunerOS::VehicleNetwork
        TunerOS::Simulator
)

foreach(target tuneros_can tuneros_can_gateway tuneros_dme tuneros_dsc tuneros_vehicle_network
               tuneros_gateway_sim)
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

    add_executable(tuneros_dsc_tests tests/dsc_test.cpp)
    target_link_libraries(tuneros_dsc_tests PRIVATE TunerOS::Dsc)

    add_executable(tuneros_vehicle_network_tests tests/vehicle_network_test.cpp)
    target_link_libraries(tuneros_vehicle_network_tests PRIVATE TunerOS::VehicleNetwork)

    add_executable(tuneros_gateway_protocol_tests tests/gateway_protocol_test.cpp)
    target_link_libraries(tuneros_gateway_protocol_tests PRIVATE TunerOS::CanGateway)

    add_executable(tuneros_fault_network_tests tests/fault_network_test.cpp)
    target_link_libraries(tuneros_fault_network_tests PRIVATE TunerOS::VehicleNetwork)

    foreach(target tuneros_can_tests tuneros_dme_frame_tests tuneros_dsc_tests
                   tuneros_vehicle_network_tests tuneros_gateway_protocol_tests
                   tuneros_fault_network_tests)
        target_compile_features(${target} PRIVATE cxx_std_20)
        if(MSVC)
            target_compile_options(${target} PRIVATE /W4 /permissive-)
        else()
            target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic)
        endif()
    endforeach()

    add_test(NAME can.contracts_transport COMMAND tuneros_can_tests)
    add_test(NAME can.dme_frames COMMAND tuneros_dme_frame_tests)
    add_test(NAME can.dsc COMMAND tuneros_dsc_tests)
    add_test(NAME can.vehicle_network COMMAND tuneros_vehicle_network_tests)
    add_test(NAME can.gateway_protocol COMMAND tuneros_gateway_protocol_tests)
    add_test(NAME can.fault_network COMMAND tuneros_fault_network_tests)
endif()
