import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot) -> None:
    """
    Executes the C3_EXCHANGE-SERIAL-L0 task.
    Strategy: Serial execution of LEFT then RIGHT.
    Sequence:
    1. LEFT deposits left_part on left_pad, clears pad, signals left_ready.
    2. RIGHT deposits right_part on right_pad, clears pad, signals right_ready.
    3. RIGHT waits for left_ready, picks up left_part, moves to left_target, releases, clears left_ready.
    4. LEFT waits for right_ready, picks up right_part, moves to right_target, releases, clears right_ready.
    5. Both arms move to departure.
    """
    
    # Constants
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    
    # Objects
    LEFT_PART = "left_part"
    RIGHT_PART = "right_part"
    
    # Poses
    LEFT_HOME = "left_home"
    RIGHT_HOME = "right_home"
    LEFT_SOURCE = "left_source"
    RIGHT_SOURCE = "right_source"
    LEFT_PAD = "left_pad"
    RIGHT_PAD = "right_pad"
    LEFT_TARGET = "left_target"
    RIGHT_TARGET = "right_target"
    LEFT_DEPART = "left_depart"
    RIGHT_DEPART = "right_depart"
    LEFT_CLEAR = "left_clear"
    RIGHT_CLEAR = "right_clear"
    
    # Events
    EVT_LEFT_READY = "left_ready"
    EVT_RIGHT_READY = "right_ready"
    
    # Timeout
    TIMEOUT = 30.0

    # --- Phase 1: LEFT Deposit ---
    # Move to source
    await robot.move(LEFT, LEFT_SOURCE, timeout_s=TIMEOUT)
    # Grasp own part
    await robot.grasp(LEFT, LEFT_PART)
    # Move to pad
    await robot.move(LEFT, LEFT_PAD, timeout_s=TIMEOUT)
    # Release on pad
    await robot.release(LEFT, LEFT_PART, LEFT_PAD)
    # Immediate departure (clear pad)
    await robot.move(LEFT, LEFT_CLEAR, timeout_s=TIMEOUT)
    # Signal ready
    left_ready_receipt = robot.signal(EVT_LEFT_READY, LEFT_PART)

    # --- Phase 2: RIGHT Deposit ---
    # Move to source
    await robot.move(RIGHT, RIGHT_SOURCE, timeout_s=TIMEOUT)
    # Grasp own part
    await robot.grasp(RIGHT, RIGHT_PART)
    # Move to pad
    await robot.move(RIGHT, RIGHT_PAD, timeout_s=TIMEOUT)
    # Release on pad
    await robot.release(RIGHT, RIGHT_PART, RIGHT_PAD)
    # Immediate departure (clear pad)
    await robot.move(RIGHT, RIGHT_CLEAR, timeout_s=TIMEOUT)
    # Signal ready
    right_ready_receipt = robot.signal(EVT_RIGHT_READY, RIGHT_PART)

    # --- Phase 3: RIGHT Consumes LEFT ---
    # Wait for peer ready
    peer_left_receipt = await robot.wait_event(EVT_LEFT_READY, timeout_s=TIMEOUT)
    # Move to pickup wait
    await robot.move(RIGHT, "right_pickup_wait", timeout_s=TIMEOUT)
    # Move to pad (approach)
    await robot.move(RIGHT, LEFT_PAD, timeout_s=TIMEOUT)
    # Grasp peer item
    await robot.grasp(RIGHT, LEFT_PART)
    # Move to target carrying receipt
    await robot.move(RIGHT, LEFT_TARGET, timeout_s=TIMEOUT, receipt=peer_left_receipt)
    # Release
    await robot.release(RIGHT, LEFT_PART, LEFT_TARGET)
    # Clear peer event
    robot.clear_event(EVT_LEFT_READY, expected_version=peer_left_receipt.version)

    # --- Phase 4: LEFT Consumes RIGHT ---
    # Wait for peer ready
    peer_right_receipt = await robot.wait_event(EVT_RIGHT_READY, timeout_s=TIMEOUT)
    # Move to pickup wait
    await robot.move(LEFT, "left_pickup_wait", timeout_s=TIMEOUT)
    # Move to pad (approach)
    await robot.move(LEFT, RIGHT_PAD, timeout_s=TIMEOUT)
    # Grasp peer item
    await robot.grasp(LEFT, RIGHT_PART)
    # Move to target carrying receipt
    await robot.move(LEFT, RIGHT_TARGET, timeout_s=TIMEOUT, receipt=peer_right_receipt)
    # Release
    await robot.release(LEFT, RIGHT_PART, RIGHT_TARGET)
    # Clear peer event
    robot.clear_event(EVT_RIGHT_READY, expected_version=peer_right_receipt.version)

    # --- Phase 5: Departure ---
    # Move to departures
    await robot.move(LEFT, LEFT_DEPART, timeout_s=TIMEOUT)
    await robot.move(RIGHT, RIGHT_DEPART, timeout_s=TIMEOUT)
