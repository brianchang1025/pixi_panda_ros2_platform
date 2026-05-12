#!/usr/bin/env python3

"""ROS 2 adapter between crisp_py gripper commands and Franka gripper actions.

This node exposes simple topics used by crisp_py and translates them into
Franka gripper action calls (open/close/grasp). It also republishes simplified
gripper state for downstream consumers.
"""

from time import time

import rclpy
from franka_msgs.action import Grasp, Homing, Move
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.node import Node
from rclpy.qos import qos_profile_system_default
from rclpy.executors import MultiThreadedExecutor
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray, Bool


class GripperClient:
    """Lightweight wrapper around Franka gripper action interfaces.

    This client handles action endpoints (`move`, `grasp`, `homing`) and tracks
    the current gripper opening width from `joint_states`.
    """

    def __init__(self, node: Node, gripper_namespace: str = "franka_gripper"):
        """Initialize the gripper client."""

        self._node = node

        # Action clients for Franka gripper primitives.
        self._move_client = ActionClient(
            node, 
            Move, 
            f"{gripper_namespace}/move",
            callback_group=ReentrantCallbackGroup(),
        )
        self._grasp_client = ActionClient(
            node,
            Grasp,
            f"{gripper_namespace}/grasp",
            callback_group=ReentrantCallbackGroup(),
        )
        self._home_client = ActionClient(
            node,
            Homing,
            f"{gripper_namespace}/homing",
            callback_group=ReentrantCallbackGroup(),
        )
        # Subscriber used to keep the latest measured finger width.
        self._gripper_state_subscriber = node.create_subscription(
            JointState,
            f"{gripper_namespace}/joint_states",
            self._gripper_state_callback,
            qos_profile_system_default,
        )
        node.get_logger().warn(self._gripper_state_subscriber.topic_name)
        self._width = None

    @property
    def width(self) -> float | None:
        """Returns the current width of the gripper or None if not initialized."""
        return self._width

    def is_open(self, open_threshold: float = 0.07) -> bool:
        """Returns True if the gripper is open."""
        return self.width > open_threshold

    def is_ready(self) -> bool:
        """Returns True if the gripper is fully ready to operate."""
        return self.width is not None

    def wait_until_ready(self, timeout_sec: float = 5.0):
        """Waits until the gripper is fully ready to operate."""
        time_start = time()
        while not self.is_ready():
            rclpy.spin_once(self._node, timeout_sec=1.0)
            if time() - time_start > timeout_sec:
                raise TimeoutError("Gripper client is not ready after timeout.")

    def _gripper_state_callback(self, msg: JointState):
        """Updates the gripper width using the current joint state."""
        self._width = msg.position[0] + msg.position[1]

    def home(self):
        """Homes the gripper."""
        goal = Homing.Goal()
        self._home_client.send_goal_async(goal)
    
    def move(self, width: float, speed: float = 0.1):
        """Move the gripper to a target width at the specified speed."""
        goal = Move.Goal()
        goal.width = width
        goal.speed = speed
        self._move_client.send_goal_async(goal)

    def grasp(
        self,
        width: float,
        speed: float = 0.1,
        force: float = 50.0,
        epsilon_outer: float = 0.08,
        epsilon_inner: float = 0.01,
        block: bool = False,
    ):
        """Grasp with the gripper and does not block.
        Args:
            width (float): The width of the gripper.
            speed (float, optional): The speed of the gripper. Defaults to 0.1.
            force (float, optional): The force of the gripper. Defaults to 50.0.
            epsilon_outer (float, optional): The outer epsilon of the gripper. Defaults to 0.08.
            epsilon_inner (float, optional): The inner epsilon of the gripper. Defaults to 0.01.
            block (bool, optional): Whether to block. Defaults to False.
        """
        goal = Grasp.Goal()
        goal.width = width
        goal.speed = speed
        goal.force = force
        goal.epsilon.outer = epsilon_outer
        goal.epsilon.inner = epsilon_inner
        future = self._grasp_client.send_goal_async(
            goal
        )  # We assume that the server is running.

        if block:
            rate = self._node.create_rate(10)
            while not future.done():
                rate.sleep()
            goal_handle = future.result()
            future = goal_handle.get_result_async()

            while not future.done():
                rate.sleep()

            rate.destroy()


    def close(self, **grasp_kwargs):
        """Close the gripper.

        Args:
            **grasp_kwargs: Keyword arguments to pass to the grasp function. (check the grasp function for details)
        """
        self.grasp(width=0.0, **grasp_kwargs)

    def open(self, **grasp_kwargs):
        """Open the gripper.

        Args:
            **grasp_kwargs: Keyword arguments to pass to the grasp function. (check the grasp function for details)
        """
        self.grasp(width=0.08, **grasp_kwargs)

    def toggle(self, **grasp_kwargs):
        """Toggle the gripper between open and closed.

        Args:
            **grasp_kwargs: Keyword arguments to pass to the grasp function. (check the grasp function for details)
        """
        if self.is_open():
            self.close(**grasp_kwargs)
        else:
            self.open(**grasp_kwargs)


class CrispPyGripperAdapater(Node):
    """Bridge node exposing crisp_py-friendly gripper control/state topics."""

    def __init__(self):
        """Configure topics, interfaces, and timers for gripper adaptation."""
        super().__init__("crisp_py_gripper_adapter")

        # Topic names expected by crisp_py and button inputs.
        self.position_command_topic = "gripper/gripper_position_commands"
        self.status_command_topic = "gripper/gripper_status_commands"
        self.joint_state_topic = "gripper/joint_states"
        self.open_close_state_topic = "gripper/open_close_states"
        self.button_right_topic = "franka_buttons/right"

        # Publish frequency for adapter state outputs.
        self.joint_state_freq = 30

        # Initialize hardware client and move to a known open state.
        self.gripper_client = GripperClient(self, gripper_namespace="panda_gripper")
        self.gripper_client.wait_until_ready()

        self.gripper_client.open()
        self.close_state = False
        self._right_button_was_pressed = False

        self.create_subscription(
            Float64MultiArray,
            self.position_command_topic,
            self.callback_position_command,
            qos_profile_system_default,
            callback_group=ReentrantCallbackGroup(),
        )

        # Command and button subscriptions.
        self.create_subscription(
            Bool,
            self.status_command_topic,
            self.callback_status_command,
            qos_profile_system_default,
            callback_group=ReentrantCallbackGroup(),
        )

        self.create_subscription(
            Bool,
            self.button_right_topic,
            self.callback_button_right,
            qos_profile_system_default,
            callback_group=ReentrantCallbackGroup(),
        )

        # State publishers consumed by crisp_py.
        self.joint_state_publisher = self.create_publisher(
            JointState,
            self.joint_state_topic,
            qos_profile_system_default,
            callback_group=ReentrantCallbackGroup(),
        )

        self.open_close_state_publisher = self.create_publisher(
            Bool,
            self.open_close_state_topic,
            qos_profile_system_default,
            callback_group=ReentrantCallbackGroup(),
        )

        # Timers that continuously publish current gripper state.
        self.timer_group = ReentrantCallbackGroup()

        self.create_timer(1 / self.joint_state_freq, self.callback_publish_joint_state, callback_group=self.timer_group)
        self.create_timer(1 / self.joint_state_freq, self.callback_publish_open_close_state, callback_group=self.timer_group)
        self.get_logger().info("The crisp_py gripper adapter started.")
        self.last_sent_width = None

    def callback_publish_joint_state(self):
        """Publish a simplified one-joint gripper state message."""
        if self.gripper_client.width is None:
            return

        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()

        msg.name = ["gripper_joint"]
        msg.position = [self.gripper_client.width]
        msg.effort = [0.0]

        self.joint_state_publisher.publish(msg)

    def callback_publish_open_close_state(self):
        """Publish whether the adapter currently considers the gripper open or closed."""
        if self.close_state is None:
            self.get_logger().warn("Open/close state is None, skipping publish.")
            return
        
        msg = Bool()
        
        msg.data = bool(self.close_state)
        self.open_close_state_publisher.publish(msg)

    def callback_position_command(self, msg: Float64MultiArray):
        """Callback to the gripper command."""
        # NOTE: this only temporaily set to control the gripper with move function.
        pass
            

    def callback_status_command(self, msg: Bool):
        """Open/close the gripper from boolean close-command topic."""
        # True = close, False = open. This is used for simple teleop control from crisp_py.
        status_command = msg.data
        if (
            status_command
            and self.gripper_client.is_open()
            and not self.close_state
        ):
            self.gripper_client.close()
            self.close_state = True
            print("Closing gripper")
        elif (
            not status_command
            and not self.gripper_client.is_open()
            and self.close_state
        ):
            self.gripper_client.open()
            self.close_state = False
            print("Opening gripper")
    

    def callback_button_right(self, msg: Bool):
        """Toggle gripper state on each right-button press (rising edge)."""
        right_button_pressed = msg.data
        if right_button_pressed :
            if not self.gripper_client.is_open():
                self.gripper_client.open()
                self.close_state = False
                print("Right button pressed: Opening gripper")
            else:
                self.gripper_client.close()
                self.close_state = True
                print("Right button pressed: Closing gripper")

        
    

def main():
    """Start the adapter node with a multithreaded executor."""
    rclpy.init()
    adapter = CrispPyGripperAdapater()
    
    # This is the "Engine" that allows multiple callbacks at once
    executor = MultiThreadedExecutor()
    executor.add_node(adapter)
    
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        adapter.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
