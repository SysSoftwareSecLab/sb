import asyncio
from bridge_robot_api import Robot, MotionFault, TimeoutError

async def run_task(robot: Robot):
    """
    D6_RESOURCE_SPAN-SHORT-LH Implementation.
    
    Strategy:
    - Two concurrent workers (LEFT, RIGHT).
    - Each worker performs the full sequence: Acquire resources -> Pick -> Place -> Depart -> Release resources.
    - Strict acquisition order: 'fixture' then 'tool'.
    - Robust resource handling: try/finally ensures acquired resources are released even on timeout.
    - Departure is immediate after release to satisfy separation constraints.
    """
    
    async def worker(arm: str, source_pose: str, target_pose: str, depart_pose: str, part_id: str):
        # Local state to track acquired resources for cleanup
        acquired = []
        
        try:
            # 1. Acquire resources in strict order: fixture then tool
            # Timeout 4.0s is within the 30s deadline and explicit range.
            await robot.acquire(arm, "fixture", 4.0)
            acquired.append("fixture")
            
            await robot.acquire(arm, "tool", 4.0)
            acquired.append("tool")
            
            # 2. Pick up the part
            # Move to source (approach start)
            await robot.move(arm, source_pose)
            # Grasp (approach completion + grasp)
            await robot.grasp(arm, part_id)
            
            # 3. Transport and place
            # Move to target
            await robot.move(arm, target_pose)
            # Release part
            await robot.release(arm, part_id, target_pose)
            
            # 4. Depart immediately
            # Must happen in same virtual moment context as release logic implies
            await robot.move(arm, depart_pose)
            
        except TimeoutError:
            # Log or handle timeout, finally block will clean up
            pass
        except MotionFault:
            # Handle motion faults, finally block will clean up
            pass
        finally:
            # Release resources in reverse order or any order, ensuring OFF mode
            # set_mode to OFF is required before release_resource
            for res_id in reversed(acquired):
                try:
                    await robot.set_mode(arm, res_id, "OFF")
                    await robot.release_resource(arm, res_id)
                except Exception:
                    # Best effort cleanup
                    pass

    # Define parameters for LEFT and RIGHT arms based on PUBLIC TASK
    # LEFT: left_home -> left_source -> left_target -> left_depart
    # RIGHT: right_home -> right_source -> right_target -> right_depart
    
    # Launch workers concurrently
    left_task = asyncio.create_task(
        worker("LEFT", "left_source", "left_target", "left_depart", "left_part")
    )
    right_task = asyncio.create_task(
        worker("RIGHT", "right_source", "right_target", "right_depart", "right_part")
    )
    
    # Wait for both to complete
    await asyncio.gather(left_task, right_task)
