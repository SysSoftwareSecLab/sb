import asyncio
from bridge_robot_api import Robot, ActionReceipt, EventReceipt, MotionFault

async def run_task(robot: Robot):
    # Configuration constants derived from PUBLIC TASK
    RES_FIXTURE = "fixture"
    RES_TOOL = "tool"
    EVENT_GATE = "rq2_gate"
    
    # Pose definitions
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
    
    OBJECTS = {
        "LEFT": "left_part",
        "RIGHT": "right_part"
    }

    async def worker(arm: str):
        """Executes the complete mission for a single arm."""
        cfg = POSES[arm]
        obj = OBJECTS[arm]
        
        # Acquire resources with safety cleanup
        acquired = []
        try:
            # 1. Acquire fixture
            await robot.acquire(arm, RES_FIXTURE, timeout_s=4.0)
            acquired.append(RES_FIXTURE)
            
            # 2. Acquire tool
            await robot.acquire(arm, RES_TOOL, timeout_s=4.0)
            acquired.append(RES_TOOL)
            
            # 3. Move to source
            await robot.move(arm, cfg["source"])
            
            # 4. Grasp part
            await robot.grasp(arm, obj)
            
            # 5. Move to target
            await robot.move(arm, cfg["target"])
            
            # 6. Release part
            await robot.release(arm, obj, cfg["target"])
            
            # 7. Depart immediately
            await robot.move(arm, cfg["depart"])
            
        finally:
            # Release any acquired resources in reverse order
            # Ensure mode is OFF before releasing
            for res in reversed(acquired):
                try:
                    await robot.set_mode(arm, res, "OFF")
                except Exception:
                    pass
                try:
                    await robot.release_resource(arm, res)
                except Exception:
                    pass

    # Experimental Structure: FOR -> IF -> PAR_JOIN
    # Variant A: Serial execution of workers
    # The loop runs once to satisfy the "one finite loop iteration" requirement.
    for _ in range(1):
        # IF: The consumer waits for the exact active receipt
        # We launch the producer (signal) and consumer (wait + work) concurrently.
        
        async def producer():
            # Signal the gate to make it active
            robot.signal(EVENT_GATE)

        async def consumer():
            # Wait for the exact active receipt
            receipt = await robot.wait_event(EVENT_GATE, timeout_s=4.0)
            
            # Execute the complete inherited mission (serial workers)
            await worker("LEFT")
            await worker("RIGHT")
            
            # Clear that version
            robot.clear_event(EVENT_GATE, expected_version=receipt.version)

        # PAR_JOIN: Concurrently join producer and consumer
        await asyncio.gather(producer(), consumer())

    # Final state check: rq2_gate inactive at return
    # The consumer cleared the event, so it is inactive.
