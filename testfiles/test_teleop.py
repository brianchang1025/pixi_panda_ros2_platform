"""
Test teleoperation script for two Franka Panda arms and grippers.

This script demonstrates a simple teleop/test setup using the crisp_py
robotics interface. It:
- Creates left and right `panda` robot instances and their grippers.
- Waits for hardware to be ready and moves both arms to a home position.
- Switches controllers to enable teleoperation (`gravity_compensation` on the
    right arm and `joint_impedance_controller` on the left).
- Synchronizes the left arm/gripper to follow the right arm/gripper state at
    ~100 Hz.
- Runs until interrupted, printing joint/gripper states, then homes and
    shuts down the robots cleanly.

Usage: run this with the project's runtime environment, for example:
        pixi run -e jazzy python scripts/testfiles/test_teleop.py
"""

import time
import numpy as np 
from crisp_py.robot import make_robot
from crisp_py.gripper.gripper import make_gripper

# %%
# INITIALIZATION: Create robot and gripper instances using crisp_py interface
# make_robot() - instantiates a robot controller for the specified arm
# make_gripper() - instantiates a gripper controller for the specified gripper
np.set_printoptions(precision=3, suppress=True)

left_arm = make_robot("panda_left")
right_arm = make_robot("panda_right")
left_gripper = make_gripper("gripper_left")
right_gripper = make_gripper("gripper_right")
left_arm.wait_until_ready()
print("Left arm is ready!")
right_arm.wait_until_ready()
print("Right arm is ready!")
left_gripper.wait_until_ready()
print("Left gripper is ready!")
right_gripper.wait_until_ready()
print("Right gripper is ready!")

# %%
# MOVE TO HOME: Use crisp_py methods to position arms and open grippers
# arm.home(blocking=True) - moves arm to home position, waits for completion
# gripper.open() - opens the gripper
print("Going to home position...")
left_arm.home(blocking=True)
left_gripper.open()
right_arm.home(blocking=True)
right_gripper.open()

time.sleep(0.5)

# CONTROLLER SWITCHING: Use crisp_py controller interface to enable teleoperation
# arm.controller_switcher_client.switch_controller() - switches to specified controller
# Gravity compensation: right arm can be moved freely with minimal effort
# Joint impedance: left arm resists but can be guided
print("Switching to teleop controllers...")
right_arm.controller_switcher_client.switch_controller("gravity_compensation")
left_arm.controller_switcher_client.switch_controller("joint_impedance_controller")


# %%
# SYNCHRONIZATION FUNCTION: Define crisp_py command execution for teleop
# arm.set_target_joint() - sends joint position commands to the arm
# arm.joint_values - reads current joint positions from arm state
# gripper.set_gripper_state() - commands gripper position
# gripper.closing_state() - reads gripper state (open/closed/intermediate)
def sync(left_arm, right_arm, left_gripper, right_gripper):
    left_arm.set_target_joint(right_arm.joint_values)
    left_gripper.set_gripper_state(right_gripper.closing_state())

# TIMER SETUP: Use crisp_py ROS node callbacks for real-time synchronization
# node.create_timer(period_sec, callback) - creates a periodic timer at ~100 Hz
# This loop continuously reads right arm state and commands it to left arm
print("Ready for teleop...")
left_arm.node.create_timer(1.0 / 100.0, lambda: sync(left_arm, right_arm, left_gripper, right_gripper))
left_gripper.node.create_timer(1.0 / 100.0, lambda: sync(left_arm, right_arm, left_gripper, right_gripper))

# MONITORING LOOP: Continuously read crisp_py state for diagnostics
# arm.joint_values - current joint positions in radians
# gripper.value - current gripper state (0.0=open, 0.04=closed)
try:
    while True:
        print(f"Left arm joint values (deg): {np.rad2deg(left_arm.joint_values)}")
        print(f"Left gripper value: {left_gripper.value}")
        
        print(f"Right arm joint values (deg): {np.rad2deg(right_arm.joint_values)}")
        print(f"Right gripper value: {right_gripper.value}")
        print("-" * 40)
        time.sleep(1.0)
except KeyboardInterrupt:
    print("User exits teleop...")
finally:
    print("Going to home position...")
    left_arm.home()
    right_arm.home()
    left_gripper.open()
    right_gripper.open()
    left_arm.shutdown()
    right_arm.shutdown()
    left_gripper.shutdown()
    right_gripper.shutdown()