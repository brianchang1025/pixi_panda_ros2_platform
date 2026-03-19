"""
Gripper teleoperation test script for two Franka Panda grippers (arms only, no joint control).

This script demonstrates bilateral gripper teleoperation using crisp_py interface.
It:
- Creates left and right gripper instances
- Waits for hardware to be ready and opens both grippers to home position
- Synchronizes the left gripper to follow the right gripper's state at ~100 Hz
- Runs until interrupted, monitoring gripper state, then opens and shuts down cleanly

NOTE: This script does NOT include arm joint teleoperation. Gripper control only.

Usage: run this with the project's runtime environment, for example:
    pixi run -e jazzy python scripts/testfiles/test_gripper_teleop.py
"""

import time
from crisp_py.gripper.gripper import make_gripper

# INITIALIZATION: Create gripper instances using crisp_py interface
# make_gripper() - instantiates a gripper controller for the specified gripper
left_gripper = make_gripper("gripper_left")

left_gripper.wait_until_ready()
print("Left gripper is ready!")

right_gripper = make_gripper("gripper_right")
right_gripper.wait_until_ready()
print("Right gripper is ready!")

# MOVE TO HOME: Use crisp_py methods to open both grippers
# gripper.open() - opens the gripper to home position
print("Going to home position...")
left_gripper.open()
right_gripper.open()
time.sleep(0.5)

left_gripper.stop()

# SYNCHRONIZATION FUNCTION: Define crisp_py command execution for bilateral gripper control
# gripper.set_gripper_state() - sends gripper position commands
# gripper.closing_state() - reads current gripper state (0.0=open, 0.04=closed)
def sync(left_gripper, right_gripper):
    left_gripper.set_gripper_state(right_gripper.closing_state())

# TIMER SETUP: Use crisp_py ROS node callbacks for real-time synchronization
# node.create_timer(period_sec, callback) - creates a periodic timer at ~100 Hz
# This loop continuously reads right gripper state and commands it to left gripper
print("Ready for teleop...")
right_gripper.node.create_timer(1.0 / 100.0, lambda: sync(left_gripper, right_gripper))

# MONITORING LOOP: Continuously read crisp_py state for diagnostics
# gripper.value - current gripper state (0.0=open, 0.04=closed)
try:
    while True:
        print(f"Left gripper value: {left_gripper.value}")
        print(f"Right gripper value: {right_gripper.value}")
        print("-" * 40)
        time.sleep(1.0)
except KeyboardInterrupt:
    print("User exits teleop...")
finally:
    print("Going to home position...")
    left_gripper.open()
    right_gripper.open()
    left_gripper.shutdown()
    right_gripper.shutdown()