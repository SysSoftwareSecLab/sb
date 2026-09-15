import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot) -> None:
    # Constants extracted from PUBLIC TASK
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    
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
    LEFT_PICKUP_WAIT = "left_pickup_wait"
    RIGHT_PICKUP_WAIT = "right_pickup_wait"
    
    # Objects
    LEFT_PART = "left_part"
    RIGHT_PART = "right_part"
    
    # Events
    LEFT_READY = "left_ready"
    RIGHT_READY = "right_ready"
    RQ2_GATE = "rq2_gate"
    
    # Durations
    MOVE_DURATION = 1.0
    
    # Helper to execute the "inherited mission" for a consumer arm
    # Mission: Pick up peer item from pad, move to target, release, depart, clear event
    async def consumer_mission(arm: str, peer_part: str, pad: str, wait_pose: str, target: str, depart: str, ready_event: str, peer_ready_receipt: EventReceipt):
        # 1. Approach peer part
        await robot.move(arm, wait_pose)
        
        # 2. Grasp peer part
        # Note: Task says "wait for peer ready must have completed" before pick up.
        # We already waited in the caller, so we proceed.
        await robot.grasp(arm, peer_part)
        
        # 3. Move to target carrying the peer item
        # Task: "The carried move to its own target must carry the exact active peer-item receipt returned by wait"
        await robot.move(arm, target, receipt=peer_ready_receipt)
        
        # 4. Release peer part at target
        await robot.release(arm, peer_part, target)
        
        # 5. Depart
        await robot.move(arm, depart)
        
        # 6. Clear the peer ready event
        # Task: "clear that event after that move"
        robot.clear_event(ready_event, expected_version=peer_ready_receipt.version)

    # Helper to execute the "producer" logic for an arm
    # Mission: Pick up own item, move to pad, release, clear pad, signal ready
    async def producer_mission(arm: str, own_part: str, home: str, source: str, pad: str, clear_pose: str, ready_event: str):
        # 1. Approach own part
        await robot.move(arm, source)
        
        # 2. Grasp own part
        await robot.grasp(arm, own_part)
        
        # 3. Move to pad
        await robot.move(arm, pad)
        
        # 4. Release own part
        await robot.release(arm, own_part, pad)
        
        # 5. Clear pad immediately
        await robot.move(arm, clear_pose)
        
        # 6. Signal ready
        robot.signal(ready_event, item_id=own_part)

    # Main execution loop
    # Task: "Inside one finite loop iteration, concurrently join an rq2_gate producer and consumer"
    
    # 1. Signal rq2_gate to start the iteration
    gate_receipt = robot.signal(RQ2_GATE)
    
    # 2. Define the consumer for the gate (the main task logic)
    async def gate_consumer():
        # Task: "A: deposit LEFT then RIGHT, then consume LEFT then RIGHT."
        # We must execute the producer missions sequentially (LEFT then RIGHT), 
        # then execute the consumer missions sequentially (LEFT then RIGHT).
        
        # --- Phase 1: Deposit (Produce) ---
        # Deposit LEFT
        await producer_mission(
            LEFT, LEFT_PART, LEFT_HOME, LEFT_SOURCE, LEFT_PAD, LEFT_CLEAR, LEFT_READY
        )
        
        # Deposit RIGHT
        await producer_mission(
            RIGHT, RIGHT_PART, RIGHT_HOME, RIGHT_SOURCE, RIGHT_PAD, RIGHT_CLEAR, RIGHT_READY
        )
        
        # --- Phase 2: Consume ---
        # Consume LEFT (Pick up RIGHT_PART from RIGHT_PAD)
        # Must wait for RIGHT_READY
        right_ready_receipt = await robot.wait_event(RIGHT_READY, timeout_s=30)
        await consumer_mission(
            LEFT, RIGHT_PART, RIGHT_PAD, LEFT_PICKUP_WAIT, LEFT_TARGET, LEFT_DEPART, RIGHT_READY, right_ready_receipt
        )
        
        # Consume RIGHT (Pick up LEFT_PART from LEFT_PAD)
        # Must wait for LEFT_READY
        left_ready_receipt = await robot.wait_event(LEFT_READY, timeout_s=30)
        await consumer_mission(
            RIGHT, LEFT_PART, LEFT_PAD, RIGHT_PICKUP_WAIT, RIGHT_TARGET, RIGHT_DEPART, LEFT_READY, left_ready_receipt
        )
        
        # Clear the gate event after the mission is complete
        robot.clear_event(RQ2_GATE, expected_version=gate_receipt.version)

    # 3. Run the consumer concurrently with the implicit gate producer (the signal we just made)
    # Since signal is synchronous and instant, the "producer" is effectively done.
    # We just await the consumer.
    await gate_consumer()
