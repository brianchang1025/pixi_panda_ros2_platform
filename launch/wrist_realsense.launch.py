#!/usr/bin/env python3
"""
Dual RealSense Camera Launch File

Launches two Intel RealSense D435i cameras simultaneously using 
ros2 realsense2_camera, distinguished by serial numbers.

Camera assignment:
  - camera_top:   Overhead fixed camera (eye-to-hand)
  - camera_wrist: Wrist-mounted camera (eye-in-hand)

Prerequisites:
  sudo apt install ros-humble-realsense2-camera
"""

from launch import LaunchDescription
from launch_ros.actions import Node


WRIST_CAMERA_SN = "_827112070502"


def generate_launch_description():
    return LaunchDescription([
        # Overhead camera (eye-to-hand)
        # Wrist camera (eye-in-hand)
        Node(
            package='realsense2_camera',
            executable='realsense2_camera_node',
            name='wrist_camera',
            namespace='camera',
            parameters=[{
                'serial_no': WRIST_CAMERA_SN,
                'camera_name': 'wrist_camera',
                'enable_color': True,
                'enable_depth': False,
                'align_depth.enable': False,
                'pointcloud.enable': False,
            }],
            output='screen'
        ),
    ])