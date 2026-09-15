import asyncio
from bridge_robot_api import Robot, MotionFault, TimeoutError

async def run_task(robot: Robot):
    """
    Executes the D6_RESOURCE_SPAN task.
    Strategy: Launch both workers concurrently. Each worker acquires 'fixture' then 'tool',
    moves to source, grasps the part, moves to target, releases the part, moves to depart,
    and finally releases resources.
    """
    async def worker(arm: str, home_pose: str, source_pose: str, target_pose: str, depart_pose: str, part_id: str):
        # Resource tracking for cleanup
        acquired_resources = []
        try:
            # 1. Acquire fixture
            await robot.acquire(arm, "fixture", timeout_s=4.0)
            acquired_resources.append("fixture")

            # 2. Acquire tool
            await robot.acquire(arm, "tool", timeout_s=4.0)
            acquired_resources.append("tool")

            # 3. Move to source (Approach)
            await robot.move(arm, source_pose)

            # 4. Grasp part
            await robot.grasp(arm, part_id)

            # 5. Move to target
            await robot.move(arm, target_pose)

            # 6. Release part
            await robot.release(arm, part_id, target_pose)

            # 7. Depart (Immediate separating departure)
            await robot.move(arm, depart_pose)

        except TimeoutError:
            # Log or handle timeout, finally block will clean up
            pass
        except MotionFault:
            # Log or handle fault, finally block will clean up
            pass
        finally:
            # Release resources in reverse order of acquisition (Tool then Fixture)
            # Ensure mode is OFF before releasing
            if "tool" in acquired_resources:
                await robot.set_mode(arm, "tool", "OFF")
                await robot.release_resource(arm, "tool")
            
            if "fixture" in acquired_resources:
                await robot.set_mode(arm, "fixture", "OFF")
                await robot.release_resource(arm, "fixture")

    # Launch both workers concurrently
    # LEFT worker
    left_task = asyncio.create_task(
        worker(
            arm="LEFT",
            home_pose="left_home",
            source_pose="left_source",
            target_pose="left_target",
            depart_pose="left_depart",
            part_id="left_part"
        )
    )

    # RIGHT worker
    right_task = asyncio.create_task(
        worker(
            arm="RIGHT",
            home_pose="right_home",
            source_pose="right_source",
            target_pose="right_target",
            depart_pose="right_depart",
            part_id="right_part"
        )
    )

    # Wait for both workers to complete
    await left_task
    await right_task
