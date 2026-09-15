import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    TOOL = "tool"
    BUFFER_LOCK = "buffer_lock"
    
    # Items and Poses
    PART_0 = "part_0"
    PART_1 = "part_1"
    
    SOURCE_0 = "source_0"
    SOURCE_1 = "source_1"
    
    BUFFER_0 = "buffer_0"
    BUFFER_1 = "buffer_1"
    
    TARGET_0 = "target_0"
    TARGET_1 = "target_1"
    
    LEFT_HOME = "left_home"
    LEFT_WAIT = "left_wait"
    RIGHT_HOME = "right_home"
    RIGHT_WAIT = "right_wait"
    
    # Events
    READY_0 = "ready_0"
    READY_1 = "ready_1"
    EMPTY_0 = "empty_0"
    RQ2_GATE = "rq2_gate"
    
    # Facts
    FACT_LINE_CLEAR = "line_clear"
    FACT_RECEIVER_READY = "receiver_ready"

    async def acquire_tool(arm: str):
        await robot.acquire(arm, TOOL, 120.0)
        await robot.set_mode(arm, TOOL, "LEFT_PROFILE" if arm == LEFT else "RIGHT_PROFILE")

    async def release_tool(arm: str):
        await robot.set_mode(arm, TOOL, "OFF")
        await robot.release_resource(arm, TOOL)

    async def producer(arm: str, item_id: str, source_pose: str, buffer_pose: str, ready_event: str):
        # 1. Acquire tool
        await acquire_tool(arm)
        
        # 2. Approach and Grasp
        await robot.move(arm, source_pose)
        await robot.grasp(arm, item_id)
        
        # 3. Move to Buffer
        await robot.acquire(arm, BUFFER_LOCK, 120.0)
        await robot.move(arm, buffer_pose)
        
        # 4. Release at Buffer
        await robot.release(arm, item_id, buffer_pose)
        
        # 5. Depart Buffer
        await robot.move(arm, LEFT_WAIT if arm == LEFT else RIGHT_WAIT)
        await robot.release_resource(arm, BUFFER_LOCK)
        
        # 6. Release Tool
        await release_tool(arm)
        
        # 7. Signal Ready
        receipt = robot.signal(ready_event, item_id)
        return receipt

    async def consumer(arm: str, item_id: str, buffer_pose: str, target_pose: str, ready_event: str, empty_event: str):
        # 1. Wait for Ready
        ready_receipt = await robot.wait_event(ready_event, 120.0)
        
        # 2. Approach and Grasp
        await robot.acquire(arm, BUFFER_LOCK, 120.0)
        await robot.move(arm, buffer_pose)
        await robot.grasp(arm, item_id)
        
        # 3. Depart Buffer
        await robot.move(arm, RIGHT_WAIT if arm == RIGHT else LEFT_WAIT)
        await robot.release_resource(arm, BUFFER_LOCK)
        
        # 4. Move to Target with Receipt
        await robot.move(arm, target_pose, receipt=ready_receipt)
        
        # 5. Clear Ready
        robot.clear_event(ready_event, expected_version=ready_receipt.version)
        
        # 6. Release at Target
        await robot.release(arm, item_id, target_pose)
        
        # 7. Depart Target
        await robot.move(arm, RIGHT_HOME if arm == RIGHT else LEFT_HOME)
        
        # 8. Signal Empty
        robot.signal(empty_event, item_id)

    async def run_serial_episode(item_id: str, source_pose: str, buffer_pose: str, target_pose: str, ready_event: str):
        # Producer
        await producer(LEFT, item_id, source_pose, buffer_pose, ready_event)
        
        # Consumer
        await consumer(RIGHT, item_id, buffer_pose, target_pose, ready_event, EMPTY_0)

    async def run_development_shape():
        # Episode 0: part_0
        await run_serial_episode(PART_0, SOURCE_0, BUFFER_0, TARGET_0, READY_0)
        
        # Episode 1: part_1
        # Wait and clear empty_0 before entering buffer
        empty_receipt = await robot.wait_event(EMPTY_0, 120.0)
        robot.clear_event(EMPTY_0, expected_version=empty_receipt.version)
        
        # Inspect both readiness facts
        obs1 = await robot.inspect(LEFT, FACT_LINE_CLEAR)
        obs2 = await robot.inspect(LEFT, FACT_RECEIVER_READY)
        
        # IF -> PAR_JOIN
        # Condition: Check if facts indicate readiness (C7 checks serially, C8 joins inside loop branch)
        # Assuming the facts indicate readiness for the loop to proceed as per "Experimental structure"
        if True: 
            # Concurrently join an rq2_gate producer and consumer
            # Producer signals rq2_gate
            # Consumer waits rq2_gate, executes inherited mission, clears version
            
            async def rq2_producer():
                # Inherited mission for producer (part_1)
                await producer(LEFT, PART_1, SOURCE_1, BUFFER_1, READY_1)
                # Signal rq2_gate
                robot.signal(RQ2_GATE, PART_1)

            async def rq2_consumer():
                # Wait for rq2_gate
                gate_receipt = await robot.wait_event(RQ2_GATE, 120.0)
                
                # Inherited mission for consumer (part_1)
                await consumer(RIGHT, PART_1, BUFFER_1, TARGET_1, READY_1, EMPTY_0)
                
                # Clear rq2_gate
                robot.clear_event(RQ2_GATE, expected_version=gate_receipt.version)

            await asyncio.gather(rq2_producer(), rq2_consumer())

    await run_development_shape()
