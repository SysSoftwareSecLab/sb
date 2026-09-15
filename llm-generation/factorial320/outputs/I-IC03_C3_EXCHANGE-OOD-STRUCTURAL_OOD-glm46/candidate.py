import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, MotionFault

async def run_task(robot: Robot) -> None:
    # Constants derived from PUBLIC TASK
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
    
    # Timeouts
    MOVE_TIMEOUT = 4.0
    EVENT_TIMEOUT = 30.0
    
    # --- Helper Functions ---
    
    async def deposit_and_signal(arm: str, part: str, source: str, pad: str, home: str, ready_event: str):
        """Moves part from source to pad, clears pad, and signals ready."""
        # 1. Approach and Grasp
        await robot.move(arm, source, timeout_s=MOVE_TIMEOUT)
        await robot.grasp(arm, part)
        
        # 2. Move to Pad
        await robot.move(arm, pad, timeout_s=MOVE_TIMEOUT)
        
        # 3. Release and Clear Pad
        await robot.release(arm, part, pad)
        # Immediate departure (clearing the pad)
        await robot.move(arm, home, timeout_s=MOVE_TIMEOUT)
        
        # 4. Signal Ready
        robot.signal(ready_event, item_id=part)

    async def consume_and_deposit(arm: str, target_part: str, pad: str, pickup_wait: str, target: str, depart: str, peer_event: str, own_event: str):
        """Waits for peer, picks up peer's part, moves to target, releases, and departs."""
        # 1. Wait for peer ready
        peer_receipt = await robot.wait_event(peer_event, timeout_s=EVENT_TIMEOUT)
        
        # 2. Approach and Grasp peer's part
        await robot.move(arm, pickup_wait, timeout_s=MOVE_TIMEOUT)
        await robot.grasp(arm, target_part)
        
        # 3. Move to Target carrying the peer receipt
        await robot.move(arm, target, timeout_s=MOVE_TIMEOUT, receipt=peer_receipt)
        
        # 4. Release at Target
        await robot.release(arm, target_part, target)
        
        # 5. Depart
        await robot.move(arm, depart, timeout_s=MOVE_TIMEOUT)
        
        # 6. Clear peer event
        robot.clear_event(peer_event, expected_version=peer_receipt.version)
        
        # 7. Clear own event (inactive at return requirement)
        # We need the version of our own event. Since we signaled it, we can infer it or wait for it.
        # The simplest way to get the version to clear is to wait for it (it's already active).
        own_receipt = await robot.wait_event(own_event, timeout_s=EVENT_TIMEOUT)
        robot.clear_event(own_event, expected_version=own_receipt.version)

    async def rq2_producer():
        """Signals the rq2_gate."""
        robot.signal(RQ2_GATE)

    async def rq2_consumer():
        """Waits for rq2_gate, then executes the full mission."""
        gate_receipt = await robot.wait_event(RQ2_GATE, timeout_s=EVENT_TIMEOUT)
        
        # Execute the complete inherited mission (Deposit then Consume)
        # Structure: FOR -> PAR_JOIN -> consumer IF
        # The loop is implicit in the single run required by the task "Inside one finite loop iteration".
        
        # Phase 1: Deposit (Parallel)
        # Left deposits left_part, Right deposits right_part
        await asyncio.gather(
            deposit_and_signal(LEFT, LEFT_PART, LEFT_SOURCE, LEFT_PAD, LEFT_HOME, LEFT_READY),
            deposit_and_signal(RIGHT, RIGHT_PART, RIGHT_SOURCE, RIGHT_PAD, RIGHT_HOME, RIGHT_READY)
        )
        
        # Phase 2: Consume (Parallel)
        # Left consumes right_part, Right consumes left_part
        await asyncio.gather(
            consume_and_deposit(LEFT, RIGHT_PART, RIGHT_PAD, LEFT_PICKUP_WAIT, RIGHT_TARGET, LEFT_DEPART, RIGHT_READY, LEFT_READY),
            consume_and_deposit(RIGHT, LEFT_PART, LEFT_PAD, RIGHT_PICKUP_WAIT, LEFT_TARGET, RIGHT_DEPART, LEFT_READY, RIGHT_READY)
        )
        
        # Clear the gate event
        robot.clear_event(RQ2_GATE, expected_version=gate_receipt.version)

    # --- Main Execution ---
    
    # PAR_JOIN the producer and consumer
    await asyncio.gather(
        rq2_producer(),
        rq2_consumer()
    )
