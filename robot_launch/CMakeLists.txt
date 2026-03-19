cmake_minimum_required(VERSION 3.5)
project(robot_launch)

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY launch
  DESTINATION share/${PROJECT_NAME}
)

install(
  PROGRAMS launch/gripper/crisp_py_gripper_adapter.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
