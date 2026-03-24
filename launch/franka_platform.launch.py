#  Copyright (c) 2025 Franka Robotics GmbH
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

############################################################################
# Parameters:
# arm_id: ID of the type of arm used (default: 'panda')
# arm_prefix: Prefix for arm topics (default: '')
# namespace: Namespace for the robot (default: '')
# urdf_file: URDF/xacro path relative to franka_description/robots (default: 'real/panda_arm.urdf.xacro')
# robot_ip: Hostname or IP address of the robot (default: '192.168.31.10')
# load_gripper: Use Franka Gripper as an end-effector (default: 'true')
# use_rviz: Launch RViz visualization (default: 'false')
# load_camera: Argument declared for camera enable/disable (default: 'true')
# third_person_camera_sn: Serial number for the third-person RealSense camera
#                         (default: env THIRD_PERSON_CAMERA_SN)
# wrist_camera_sn: Serial number for the wrist RealSense camera
#                  (default: env WRIST_CAMERA_SN)
# use_fake_hardware: Use fake hardware (default: 'false')
# fake_sensor_commands: Fake sensor commands (default: 'false')
# joint_state_rate: Rate for joint state publishing in Hz (default: '30')
# controllers_yaml: Controller config file path
#                   (default: franka_bringup/config/controllers.yaml)
#
# Paragraph 1 — Purpose
# This launch file brings up a complete Franka platform runtime for one robot.
# It generates `robot_description` from xacro, starts ros2_control,
# starts state publishers, and spawns default controllers.
#
# Paragraph 2 — Optional runtime pieces
# If `load_gripper:=true`, it launches Franka gripper support and
# `crisp_py_gripper_adapter.py`. If `use_rviz:=true`, it launches RViz.
# It also starts two RealSense nodes (third-person and wrist) in namespace
# `camera` using `third_person_camera_sn` and `wrist_camera_sn`.
#
# Paragraph 3 — Camera argument note
# `load_camera` is currently declared as a launch argument but is not yet used
# as a condition to enable/disable camera nodes in this file.
#
# Paragraph 4 — Example usage
# ros2 launch franka_bringup franka_platform.launch.py robot_ip:=192.168.31.10 load_gripper:=true
#
# Paragraph 5 — Where to find the package share launch file
# Source workspace path:
#   src/franka_bringup/launch/franka_platform.launch.py
# Installed package share path pattern:
#   <prefix>/share/franka_bringup/launch/franka_platform.launch.py
# To print `<prefix>`:
#   ros2 pkg prefix franka_bringup
#
# This is an error-prone command line; you may prefer to write parameters into a YAML file like:
#   franka_bringup/config/franka.config.yaml
# That is especially useful if you want to use multiple namespaces.
# In that case, it's not possible to specify the parameters on the command line,
# since each parameter would have to be somehow isolated or prefixed by the namespace.
# then later parsed by the launch file.
# See: example.launch.py for more details.
#
# You may wish to experiment with the namespace parameter to see how it affects topic names
# and service names. The default namespace is empty, which means that the
# topics and services are not namespaced. If you set the namespace to 'franka1',
# the topics and services will be namespaced with 'franka1'. For example, the
# joint_state_publisher will publish to '/franka1/joint_states' instead of '/joint_states'.
# and the controller_manager will look for the controllers in the 'franka1' namespace.
# To see the difference you can run the following command:
#   ros2 topic list | grep joint_states
#   ros2 service list | grep controller_manager
# This becomes useful, for example, when you require multiple Franka robots doing
# possibly different but related tasks. So, you might have the "PICK" and "PLACE" robots
# in the same workspace, but they are not supposed to interfere with each other.
#
# This script generates the robot description from the selected xacro file and
# integrates controllers.yaml for controller manager configuration. It can be
# launched directly or included by higher-level launch files. Ensure the selected
# urdf_file exists in franka_description/robots to avoid runtime errors.
#
# This approach improves upon earlier launch scripts, which often lacked namespace
# support and were less modular, offering a more consistent and maintainable solution.
# While some may prefer older scripts for simplicity in specific scenarios,
# franka_platform.launch.py provides a more consistent and scalable baseline
# for this workspace.
############################################################################


from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.actions import OpaqueFunction, Shutdown
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, EnvironmentVariable
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
import xacro

# Build the runtime node list for the Franka platform launch.
# This function resolves launch arguments, generates robot_description from xacro,
# and returns all Nodes/Includes to start.


def generate_robot_nodes(context):

    # Read launch argument `load_gripper` as a raw string from the current launch context.
    # We keep the raw value because xacro mapping expects string-like input.

    load_gripper_launch_configuration = LaunchConfiguration("load_gripper").perform(
        context
    )
    # Convert the same argument into a Python boolean for regular conditional logic.
    load_gripper = load_gripper_launch_configuration.lower() == "true"

    # Resolve the URDF/Xacro absolute path from:
    #   <share>/franka_description/robots/<urdf_file argument>
    urdf_path = PathJoinSubstitution(
        [
            FindPackageShare("franka_description"),
            "robots",
            LaunchConfiguration("urdf_file"),
        ]
    ).perform(context)

    # Generate the full robot description XML by processing the selected xacro file.
    # The mappings below inject runtime launch parameters into the xacro template.
    robot_description = xacro.process_file(
        urdf_path,
        mappings={
            # Arm model identifier used by xacro.
            "arm_id": LaunchConfiguration("arm_id").perform(context),
            # Robot network address passed into hardware configuration.
            "robot_ip": LaunchConfiguration("robot_ip").perform(context),
            # Xacro hand flag is passed as text ("true"/"false").
            "hand": load_gripper_launch_configuration,
            # Enable fake ros2_control hardware backend when requested.
            "use_fake_hardware": LaunchConfiguration("use_fake_hardware").perform(
                context
            ),
            # Allow fake command interfaces when using fake hardware.
            "fake_sensor_commands": LaunchConfiguration("fake_sensor_commands").perform(
                context
            ),
        },
    ).toprettyxml(indent="  ")

    # Namespace all runtime nodes when `namespace` is provided.
    namespace = LaunchConfiguration("namespace").perform(context)

    # Controller manager YAML path (can be overridden by launch argument).
    controllers_yaml = LaunchConfiguration("controllers_yaml").perform(context)

    # Joint state sources merged by joint_state_publisher:
    # robot arm state + optional gripper state.
    joint_state_publisher_sources = [
        "franka/joint_states",
        "panda_gripper/joint_states",
    ]
    # Publishing rate for joint_state_publisher.
    joint_state_rate = int(LaunchConfiguration("joint_state_rate").perform(context))

    # Build the runtime node list returned to OpaqueFunction.
    nodes = [
        # Publish TF and robot state from robot_description.
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            namespace=namespace,
            parameters=[{"robot_description": robot_description}],
            output="screen",
        ),
        # Start ros2_control controller manager and load controller parameters.
        # If this core node exits, shut down the entire launch system.
        Node(
            package="controller_manager",
            executable="ros2_control_node",
            namespace=namespace,
            parameters=[
                controllers_yaml,
                {"robot_description": robot_description},
                {"load_gripper": load_gripper},
            ],
            # Ensure controller manager consumes the Franka joint state topic name.
            remappings=[("joint_states", joint_state_publisher_sources[0])],
            output="screen",
            on_exit=Shutdown(),
        ),
        # Merge configured joint state sources into one `joint_states` stream.
        Node(
            package="joint_state_publisher",
            executable="joint_state_publisher",
            name="joint_state_publisher",
            namespace=namespace,
            parameters=[
                {
                    # Source topics for aggregation.
                    "source_list": joint_state_publisher_sources,
                    # Output publish rate.
                    "rate": joint_state_rate,
                    # Skip reading URDF from parameter, since source_list is used.
                    "use_robot_description": False,
                }
            ],
            output="screen",
        ),
        # Spawn always-on joint state broadcaster controller.
        Node(
            package="controller_manager",
            executable="spawner",
            namespace=namespace,
            arguments=["joint_state_broadcaster"],
            output="screen",
        ),
        # Spawn pose broadcaster controller.
        Node(
            package="controller_manager",
            executable="spawner",
            namespace=namespace,
            arguments=["pose_broadcaster"],
            output="screen",
        ),
        # Spawn cartesian impedance controller in inactive state.
        Node(
            package="controller_manager",
            executable="spawner",
            namespace=namespace,
            arguments=["cartesian_impedance_controller", "--inactive"],
            output="screen",
        ),
        # Spawn gravity compensation controller in inactive state.
        Node(
            package="controller_manager",
            executable="spawner",
            namespace=namespace,
            arguments=["gravity_compensation", "--inactive"],
            output="screen",
        ),
        # Spawn joint impedance controller in inactive state.
        Node(
            package="controller_manager",
            executable="spawner",
            namespace=namespace,
            arguments=["joint_impedance_controller", "--inactive"],
            output="screen",
        ),
        # Spawn joint trajectory controller in inactive state.
        Node(
            package="controller_manager",
            executable="spawner",
            namespace=namespace,
            arguments=["joint_trajectory_controller", "--inactive"],
            output="screen",
        ),
        # Include Franka gripper launch file when gripper support is enabled.
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                [
                    PathJoinSubstitution(
                        [
                            FindPackageShare("franka_gripper"),
                            "launch",
                            "gripper.launch.py",
                        ]
                    )
                ]
            ),
            launch_arguments={
                # Pass through namespace to keep topic layout consistent.
                "namespace": namespace,
                # Pass through robot IP for gripper hardware connection.
                "robot_ip": LaunchConfiguration("robot_ip").perform(context),
                # Keep fake hardware setting aligned with main robot launch.
                "use_fake_hardware": LaunchConfiguration("use_fake_hardware").perform(
                    context
                ),
            }.items(),
            condition=IfCondition(LaunchConfiguration("load_gripper")),
        ),
        # Start crisp_py adapter only when gripper is enabled.
        Node(
                package="franka_bringup",
                executable="crisp_py_gripper_adapter.py",
                name="crisp_py_gripper_adapter",
                namespace=namespace,
                output="screen",
                condition=IfCondition(LaunchConfiguration("load_gripper")),
        ),
        # Franka Button node for reading robot button states.
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                [
                    PathJoinSubstitution(
                        [
                            FindPackageShare("franka_buttons"),
                            "launch",
                            "button_to_record_msg.launch.py",
                        ]
                    )
                ]
            ),
            launch_arguments={
                # Pass through namespace to keep topic layout consistent.
                "namespace": namespace,
                # Pass through robot IP for button hardware connection.
                "robot_ip": LaunchConfiguration("robot_ip").perform(context),
            }.items(),
            condition=IfCondition(LaunchConfiguration("buttons_enabled")),
        ),
        
        # Optional RViz visualization with Franka default display config.
        Node(
            package="rviz2",
            executable="rviz2",
            name="rviz2",
            namespace=namespace,
            arguments=[
                "--display-config",
                PathJoinSubstitution(
                    [
                        FindPackageShare("franka_description"),
                        "rviz",
                        "visualize_franka.rviz",
                    ]
                ),
            ],
            condition=IfCondition(LaunchConfiguration("use_rviz")),
        ),
        # Third-person RealSense camera node.
        Node(
            package='realsense2_camera',
            executable='realsense2_camera_node',
            name='third_person_camera',
            namespace='camera',
            parameters=[{
                # Camera serial number (typically from environment-backed launch arg).
                'serial_no': LaunchConfiguration("third_person_camera_sn").perform(context),
                'camera_name': 'third_person_camera',
                # Enable RGB stream.
                'enable_color': True,
                # Enable depth stream.
                'enable_depth': True,
                # Align depth image to color frame.
                'align_depth.enable': True,
                # Enable point cloud output from depth stream.
                'pointcloud.enable': True,
            }],
            output='screen',
            condition=IfCondition(LaunchConfiguration("load_camera")),
        ),
        # Wrist camera (eye-in-hand) RealSense node.
        Node(
            package='realsense2_camera',
            executable='realsense2_camera_node',
            name='wrist_camera',
            namespace='camera',
            parameters=[{
                # Camera serial number (typically from environment-backed launch arg).
                'serial_no': LaunchConfiguration("wrist_camera_sn").perform(context),
                'camera_name': 'wrist_camera',
                # Enable RGB stream.
                'enable_color': True,
                # Enable depth stream.
                'enable_depth': True,
                # Align depth image to color frame.
                'align_depth.enable': True,
                # Enable point cloud output from depth stream.
                'pointcloud.enable': True,
            }],
            output='screen',
            condition=IfCondition(LaunchConfiguration("load_camera")),
        ),
    ]

    # Return all launch entities to the caller (OpaqueFunction).
    return nodes


# The generate_launch_description function is the entry point (like "main")
# We use it to declare the launch arguments and call the generate_robot_nodes function.


def generate_launch_description():
    launch_args = [
        DeclareLaunchArgument(
            "arm_id", default_value="panda", description="ID of the type of arm used"
        ),
        DeclareLaunchArgument(
            "arm_prefix", default_value="", description="Prefix for arm topics"
        ),
        DeclareLaunchArgument(
            "namespace", default_value="", description="Namespace for the robot"
        ),
        DeclareLaunchArgument(
            "urdf_file",
            default_value="real/panda_arm.urdf.xacro",
            description="Path to URDF file",
        ),
        DeclareLaunchArgument(
            "robot_ip",
            default_value="192.168.31.10",
            description="Hostname or IP address of the robot",
        ),
        DeclareLaunchArgument(
            "load_gripper",
            default_value="true",
            description="Use Franka Gripper as an end-effector",
        ),
        DeclareLaunchArgument(
            "buttons_enabled",
            default_value="true",
            description="Enable Franka Button support for recording and control gripper",
        ),
        DeclareLaunchArgument(
            "use_rviz",
            default_value="false",
            description="Visualize the robot in RViz",
        ),
        DeclareLaunchArgument(
            "load_camera",
            default_value="false",
            description="Launch dual realsense cameras",
        ),
        DeclareLaunchArgument(
            "third_person_camera_sn",
            default_value=EnvironmentVariable("THIRD_PERSON_CAMERA_SN", default_value=""),
            description="Serial number of the third person camera",
        ),
        DeclareLaunchArgument(
            "wrist_camera_sn",
            default_value=EnvironmentVariable("WRIST_CAMERA_SN", default_value=""),
            description="Serial number of the wrist camera",
        ),
        DeclareLaunchArgument(
            "use_fake_hardware", default_value="false", description="Use fake hardware"
        ),
        DeclareLaunchArgument(
            "fake_sensor_commands",
            default_value="false",
            description="Fake sensor commands",
        ),
        DeclareLaunchArgument(
            "joint_state_rate",
            default_value="30",
            description="Rate for joint state publishing (Hz)",
        ),
        DeclareLaunchArgument(
            "controllers_yaml",
            default_value=PathJoinSubstitution(
                [FindPackageShare("franka_bringup"), "config", "controllers.yaml"]
            ),
            description="Override the default controllers.yaml file.",
        ),
    ]

    return LaunchDescription(
        launch_args + [OpaqueFunction(function=generate_robot_nodes)]
    )
