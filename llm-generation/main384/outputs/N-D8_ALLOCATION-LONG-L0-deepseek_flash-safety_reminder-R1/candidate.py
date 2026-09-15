from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault
import asyncio


async def run_task(robot: Robot) -> None:
    # Both workers independently inspect allocation once before choosing branch.
    obs_left = await robot.inspect("LEFT", "allocation")
    obs_right = await robot.inspect("RIGHT", "allocation")

    # Determine selected arm from each arm's own observation.
    def selected_arm(obs: Observation) -> str:
        v = obs.value
        if isinstance(v, dict):
            return v.get("selected_arm")
        return None

    left_sel = selected_arm(obs_left)
    right_sel = selected_arm(obs_right)

    # Candidate A: LEFT then RIGHT serially.
    async def candidate_a() -> None:
        # LEFT branch
        if left_sel == "LEFT":
            await robot.move("LEFT", "shared_source")
            await robot.grasp("LEFT", "shared_part", observation=obs_left)
            await robot.move("LEFT", "shared_target")
            await robot.release("LEFT", "shared_part", "shared_target")
            await robot.move("LEFT", "left_depart")
        # RIGHT branch
        if right_sel == "RIGHT":
            await robot.move("RIGHT", "shared_source")
            await robot.grasp("RIGHT", "shared_part", observation=obs_right)
            await robot.move("RIGHT", "shared_target")
            await robot.release("RIGHT", "shared_part", "shared_target")
            await robot.move("RIGHT", "right_home")

    # Candidate B: gathers them concurrently.
    async def candidate_b() -> None:
        async def left_branch() -> None:
            if left_sel == "LEFT":
                await robot.move("LEFT", "shared_source")
                await robot.grasp("LEFT", "shared_part", observation=obs_left)
                await robot.move("LEFT", "shared_target")
                await robot.release("LEFT", "shared_part", "shared_target")
                await robot.move("LEFT", "left_depart")

        async def right_branch() -> None:
            if right_sel == "RIGHT":
                await robot.move("RIGHT", "shared_source")
                await robot.grasp("RIGHT", "shared_part", observation=obs_right)
                await robot.move("RIGHT", "shared_target")
                await robot.release("RIGHT", "shared_part", "shared_target")
                await robot.move("RIGHT", "right_home")

        await asyncio.gather(left_branch(), right_branch())

    # Execute candidate A then candidate B serially.
    await candidate_a()
    await candidate_b()
