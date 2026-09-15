import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, MotionFault

async def run_task(robot: Robot) -> None:
    # Constants
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    
    # Poses
    LEFT_HOME = "left_home"
    LEFT_SOURCE = "left_source"
    LEFT_PAD = "left_pad"
    LEFT_PICKUP_WAIT = "left_pickup_wait"
    LEFT_TARGET = "left_target"
    LEFT_CLEAR = "left_clear"
    LEFT_DEPART = "left_depart"
    
    RIGHT_HOME = "right_home"
    RIGHT_SOURCE = "right_source"
    RIGHT_PAD = "right_pad"
    RIGHT_PICKUP_WAIT = "right_pickup_wait"
    RIGHT_TARGET = "right_target"
    RIGHT_CLEAR = "right_clear"
    RIGHT_DEPART = "right_depart"
    
    # Objects
    LEFT_PART = "left_part"
    RIGHT_PART = "right_part"
    
    # Events
    LEFT_READY = "left_ready"
    RIGHT_READY = "right_ready"
    RQ2_GATE = "rq2_gate"
    
    # Resources
    RQ2_GAP_0 = "rq2_gap_0"
    RQ2_GAP_1 = "rq2_gap_1"
    RQ2_GAP_2 = "rq2_gap_2"
    
    TIMEOUT_S = 4.0
    
    # --- RQ2_GATE Producer/Consumer Logic (Serial) ---
    # Acquire resources in numeric order with LEFT
    await robot.acquire(LEFT, RQ2_GAP_0, TIMEOUT_S)
    await robot.acquire(LEFT, RQ2_GAP_1, TIMEOUT_S)
    await robot.acquire(LEFT, RQ2_GAP_2, TIMEOUT_S)
    
    # Signal rq2_gate
    gate_receipt = robot.signal(RQ2_GATE)
    
    # Wait for rq2_gate immediately after signal
    # The receipt returned by wait must be used for the protected scope
    active_gate_receipt = await robot.wait_event(RQ2_GATE, TIMEOUT_S)
    
    # --- Inherited Dual-Arm Mission (Serial) ---
    # Phase 1: Deposit LEFT
    # Approach and Grasp left_part
    await robot.move(LEFT, LEFT_SOURCE, timeout_s=TIMEOUT_S)
    await robot.grasp(LEFT, LEFT_PART)
    
    # Move to left_pad and Release
    await robot.move(LEFT, LEFT_PAD, timeout_s=TIMEOUT_S)
    await robot.release(LEFT, LEFT_PART, LEFT_PAD)
    
    # Immediate departure (clear the pad)
    await robot.move(LEFT, LEFT_CLEAR, timeout_s=TIMEOUT_S)
    
    # Publish left_ready
    robot.signal(LEFT_READY)
    
    # Phase 2: Deposit RIGHT
    # Approach and Grasp right_part
    await robot.move(RIGHT, RIGHT_SOURCE, timeout_s=TIMEOUT_S)
    await robot.grasp(RIGHT, RIGHT_PART)
    
    # Move to right_pad and Release
    await robot.move(RIGHT, RIGHT_PAD, timeout_s=TIMEOUT_S)
    await robot.release(RIGHT, RIGHT_PART, RIGHT_PAD)
    
    # Immediate departure (clear the pad)
    await robot.move(RIGHT, RIGHT_CLEAR, timeout_s=TIMEOUT_S)
    
    # Publish right_ready
    robot.signal(RIGHT_READY)
    
    # Phase 3: Consume LEFT (Pick up right_part from right_pad)
    # Wait for peer ready (right_ready)
    peer_ready_receipt = await robot.wait_event(RIGHT_READY, TIMEOUT_S)
    
    # Move to pickup wait pose
    await robot.move(LEFT, LEFT_PICKUP_WAIT, timeout_s=TIMEOUT_S)
    
    # Approach and Grasp right_part
    await robot.move(LEFT, RIGHT_PAD, timeout_s=TIMEOUT_S)
    await robot.grasp(LEFT, RIGHT_PART)
    
    # Move to left_target carrying the peer receipt
    await robot.move(LEFT, LEFT_TARGET, timeout_s=TIMEOUT_S, receipt=peer_ready_receipt)
    
    # Clear the peer event after the move
    robot.clear_event(RIGHT_READY, expected_version=peer_ready_receipt.version)
    
    # Release right_part at left_target
    await robot.release(LEFT, RIGHT_PART, LEFT_TARGET)
    
    # Phase 4: Consume RIGHT (Pick up left_part from left_pad)
    # Wait for peer ready (left_ready)
    peer_ready_receipt = await robot.wait_event(LEFT_READY, TIMEOUT_S)
    
    # Move to pickup wait pose
    await robot.move(RIGHT, RIGHT_PICKUP_WAIT, timeout_s=TIMEOUT_S)
    
    # Approach and Grasp left_part
    await robot.move(RIGHT, LEFT_PAD, timeout_s=TIMEOUT_S)
    await robot.grasp(RIGHT, LEFT_PART)
    
    # Move to right_target carrying the peer receipt
    await robot.move(RIGHT, RIGHT_TARGET, timeout_s=TIMEOUT_S, receipt=peer_ready_receipt)
    
    # Clear the peer event after the move
    robot.clear_event(LEFT_READY, expected_version=peer_ready_receipt.version)
    
    # Release left_part at right_target
    await robot.release(RIGHT, LEFT_PART, RIGHT_TARGET)
    
    # --- Finalization ---
    # Move arms to departure
    await robot.move(LEFT, LEFT_DEPART, timeout_s=TIMEOUT_S)
    await robot.move(RIGHT, RIGHT_DEPART, timeout_s=TIMEOUT_S)
    
    # Clear rq2_gate after the mission
    robot.clear_event(RQ2_GATE, expected_version=active_gate_receipt.version)
    
    # Release resources (ensure mode is OFF, which is initial and default)
    await robot.release_resource(LEFT, RQ2_GAP_0)
    await robot.release_resource(LEFT, RQ2_GAP_1)
    await robot.release_resource(LEFT, RQ2_GAP_2)
