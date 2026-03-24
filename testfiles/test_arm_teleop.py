"""
Arm teleoperation test script for two Franka Panda arms (no grippers).

This script demonstrates bilateral arm teleoperation using crisp_py interface.
It:
- Creates left and right panda robot instances
- Waits for hardware to be ready and moves both arms to home position
- Switches controllers to enable teleoperation (joint_impedance_controller on left arm,
  gravity_compensation on right arm)
- Synchronizes the left arm to follow the right arm's joint positions at ~100 Hz
- Runs until interrupted, monitoring joint state, then homes and shuts down cleanly

NOTE: This script does NOT include teleoperation for grippers. Joint control only.

Usage: run this with the project's runtime environment, for example:
    pixi run -e jazzy python scripts/testfiles/test_arm_teleop.py
"""

import time
from crisp_py.robot import make_robot

# %%
# INITIALIZATION: Create robot instances using crisp_py interface
# make_robot() - instantiates a robot controller for the specified arm
left_arm = make_robot("panda_left")
right_arm = make_robot("panda_right")
left_arm.wait_until_ready()
right_arm.wait_until_ready()

# %%
# MOVE TO HOME: Use crisp_py methods to position both arms
# arm.home(blocking=True) - moves arm to home position, waits for completion
print("Going to home position...")
left_arm.home(blocking=True)
right_arm.home(blocking=True)

#left_arm.controller_switcher_client.deactivate_all_motion_controllers()
#right_arm.controller_switcher_client.deactivate_all_motion_controllers()

time.sleep(0.5)

# CONTROLLER SWITCHING: Use crisp_py controller interface for bilateral teleoperation
# arm.controller_switcher_client.switch_controller() - switches to specified controller
# Gravity compensation: right arm can be moved freely with minimal effort (primary/lead arm)
# Joint impedance: left arm resists but can be guided (follower/secondary arm)
print("Switching to teleop controllers...")
right_arm.controller_switcher_client.switch_controller("gravity_compensation")
left_arm.controller_switcher_client.switch_controller("joint_impedance_controller")


# %%
# SYNCHRONIZATION FUNCTION: Define crisp_py command execution for bilateral control
# arm.set_target_joint() - sends joint position commands to the arm
# arm.joint_values - reads current joint positions from arm state
def sync(left_arm, right_arm):
    left_arm.set_target_joint(right_arm.joint_values)

# TIMER SETUP: Use crisp_py ROS node callbacks for real-time synchronization
# node.create_timer(period_sec, callback) - creates a periodic timer at ~100 Hz
# This loop continuously reads right arm state and commands it to left arm
print("Ready for teleop...")
right_arm.node.create_timer(1.0 / 100.0, lambda: sync(left_arm, right_arm))

# MONITORING LOOP: Continuously read crisp_py state for diagnostics
# arm.joint_values - current joint positions in radians
try:
    while True:
        print(f"Left arm joint values: {left_arm.joint_values}")
        print(f"Right arm joint values: {right_arm.joint_values}")
        print("-" * 40)
        time.sleep(1.0)
except KeyboardInterrupt:
    print("User exits teleop...")
finally:
    # CLEANUP: Use crisp_py shutdown methods for graceful termination
    # arm.home() - moves arm back to home position
    # arm.shutdown() - closes connection and releases robot resources
    print("Going to home position...")
    left_arm.home()
    right_arm.home()
    left_arm.shutdown()
    right_arm.shutdown()