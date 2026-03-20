import launch
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    robot_ip = LaunchConfiguration("robot_ip", default="")
    namespace = LaunchConfiguration("namespace", default="")
    launch_arguments = [DeclareLaunchArgument("robot_ip", default_value=""),
                        DeclareLaunchArgument("namespace", default_value="")]

    return launch.LaunchDescription(
        [
            *launch_arguments,
            Node(
                package="franka_buttons",
                executable="franka_pilot_buttons",
                namespace=namespace,
                parameters=[
                    {
                        "hostname": robot_ip,
                        "credentials_filepath": ".env",
                        "request_timeout": 2.0,
                    },
                ],
            ),
            Node(
                package="franka_buttons",
                name="franka_buttons_to_record",
                executable="franka_buttons_to_record",
                namespace=namespace,
            ),
        ],
    )
