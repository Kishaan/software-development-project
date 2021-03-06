cmake_minimum_required(VERSION 2.8.3)
project(mcr_object_list_merger)

find_package(catkin REQUIRED
  COMPONENTS
    roscpp
    roslint
    mcr_scene_segmentation
    mcr_perception_msgs
    mir_knowledge_base_analyzer
)


catkin_package(
  CATKIN_DEPENDS
    mcr_perception_msgs
    mcr_scene_segmentation
    mir_knowledge_base_analyzer
    tf
)

include_directories(
  ros/include
  ${catkin_INCLUDE_DIRS}
)

add_executable(object_list_merger
  ros/src/object_list_merger.cpp
)

add_dependencies(object_list_merger
  ${catkin_EXPORTED_TARGETS}
)

target_link_libraries(object_list_merger
  ${catkin_LIBRARIES}
)

roslint_cpp()

### TESTS
if(CATKIN_ENABLE_TESTING)
  find_package(roslaunch REQUIRED)
  roslaunch_add_file_check(ros/launch)
endif()

install(TARGETS object_list_merger
  RUNTIME DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

install(DIRECTORY ros/launch/
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/ros/launch
)
