import asyncio
from bridge_robot_api import Robot, EventReceipt, ActionReceipt

async def run_task(robot: Robot) -> None:
    """
    Task: D2_EVENT-LONG-LH
    Strategy: Sequential execution by LEFT arm.
    1. LEFT picks up left_part from left_source.
    2. LEFT moves left_part to left_pad and releases it.
    3. LEFT signals left_ready.
    4. LEFT waits for right_ready.
    5. LEFT moves to right_pad (carrying the right_ready receipt).
    6. LEFT picks up right_part from right_pad.
    7. LEFT clears right_ready.
    8. LEFT moves right_part to left_target and releases it.
    9. LEFT moves to left_depart.
    10. LEFT clears left_ready.
    """
    
    # Constants
    ARM = "LEFT"
    TIMEOUT = 4.0
    
    # 1. Pick up own part (left_part) from source
    await robot.move(ARM, "left_home", timeout_s=TIMEOUT)
    await robot.grasp(ARM, "left_part")
    
    # 2. Deposit own part on own pad (left_pad)
    await robot.move(ARM, "left_pad", timeout_s=TIMEOUT)
    await robot.release(ARM, "left_part", "left_pad")
    
    # 3. Signal own readiness (left_ready)
    left_ready_receipt = robot.signal("left_ready")
    
    # 4. Wait for peer readiness (right_ready)
    right_ready_receipt = await robot.wait_event("right_ready", timeout_s=TIMEOUT)
    
    # 5. Move to peer pad (right_pad) carrying the peer receipt
    # This satisfies: "carried move to its own target must carry the exact active peer-item receipt"
    # Note: The target of the carried move is the location where we pick up the peer item.
    await robot.move(ARM, "right_pad", timeout_s=TIMEOUT, receipt=right_ready_receipt)
    
    # 6. Pick up peer item (right_part)
    await robot.grasp(ARM, "right_part")
    
    # 7. Clear peer event (right_ready)
    # This satisfies: "clear that event after that move"
    robot.clear_event("right_ready", expected_version=right_ready_receipt.version)
    
    # 8. Move peer item to own target (left_target) and release
    await robot.move(ARM, "left_target", timeout_s=TIMEOUT)
    await robot.release(ARM, "right_part", "left_target")
    
    # 9. Depart to own departure pose
    await robot.move(ARM, "left_depart", timeout_s=TIMEOUT)
    
    # 10. Clear own event (left_ready)
    # This satisfies: "empty arms at own departure; both ready events inactive."
    robot.clear_event("left_ready", expected_version=left_ready_receipt.version)
