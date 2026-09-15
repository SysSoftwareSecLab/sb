import asyncio
from bridge_robot_api import Robot, ActionReceipt, EventReceipt, MotionFault

async def run_task(robot: Robot):
    # Constants extracted from PUBLIC TASK
    RES_FIXTURE = "fixture"
    RES_TOOL = "tool"
    EVENT_GATE = "rq2_gate"
    
    POSES = {
        "LEFT": {
            "home": "left_home",
            "source": "left_source",
            "target": "left_target",
            "depart": "left_depart"
        },
        "RIGHT": {
            "home": "right_home",
            "source": "right_source",
            "target": "right_target",
            "depart": "right_depart"
        }
    }
    
    PARTS = {
        "LEFT": "left_part",
        "RIGHT": "right_part"
    }

    async def acquire_resources(arm: str):
        """Acquire fixture then tool. Ensures release on timeout."""
        acquired = []
        try:
            # Acquire fixture
            await robot.acquire(arm, RES_FIXTURE, timeout_s=4.0)
            acquired.append(RES_FIXTURE)
            
            # Acquire tool
            await robot.acquire(arm, RES_TOOL, timeout_s=4.0)
            acquired.append(RES_TOOL)
            
        except Exception:
            # Release any successfully acquired resources on failure/timeout
            for res_id in acquired:
                # Ensure mode is OFF before releasing (initial mode is OFF, and we don't change it)
                await robot.release_resource(arm, res_id)
            raise

    async def release_resources(arm: str):
        """Release tool then fixture."""
        await robot.release_resource(arm, RES_TOOL)
        await robot.release_resource(arm, RES_FIXTURE)

    async def worker(arm: str):
        """Execute the complete mission for one arm."""
        p_id = PARTS[arm]
        poses = POSES[arm]
        
        # 1. Move to home (start of approach sequence)
        await robot.move(arm, poses["home"])
        
        # 2. Approach source (part of approach sequence)
        await robot.move(arm, poses["source"])
        
        # 3. Grasp part (must follow approach immediately)
        await robot.grasp(arm, p_id)
        
        # 4. Acquire resources (Fixture then Tool)
        await acquire_resources(arm)
        
        try:
            # 5. Move to target while owning both
            await robot.move(arm, poses["target"])
            
            # 6. Release part
            await robot.release(arm, p_id, poses["target"])
            
            # 7. Depart (immediate separating departure)
            await robot.move(arm, poses["depart"])
            
        finally:
            # 8. Release resources (Tool then Fixture)
            await release_resources(arm)

    # Main execution structure
    # "A runs the two complete workers serially."
    # "Inside one finite loop iteration, concurrently join an rq2_gate producer and consumer..."
    
    # We run one iteration of the finite loop.
    # Producer: Signal the gate.
    # Consumer: Wait for the gate, then run the mission, then clear the gate.
    
    async def producer():
        robot.signal(EVENT_GATE)
    
    async def consumer():
        # Wait for the exact active receipt
        receipt = await robot.wait_event(EVENT_GATE, timeout_s=4.0)
        
        # Execute the complete inherited mission
        # Since A runs workers serially, we run LEFT then RIGHT.
        await worker("LEFT")
        await worker("RIGHT")
        
        # Clear that version
        robot.clear_event(EVENT_GATE, expected_version=receipt.version)

    # PAR_JOIN: Run producer and consumer concurrently
    await asyncio.gather(producer(), consumer())
