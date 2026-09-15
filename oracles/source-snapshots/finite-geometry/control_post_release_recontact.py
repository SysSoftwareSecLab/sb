"""Self-authored tool fixture: valid departure followed by forbidden recontact."""


async def run_task(robot):
    initial_tile_pose = await robot.inspect("RIGHT", "tile_pose")
    await robot.move("LEFT", "fixture_source")
    await robot.grasp("LEFT", "locator_fixture")
    await robot.move("LEFT", "fixture_ready")
    await robot.release("LEFT", "locator_fixture", "fixture_ready")
    await robot.move("LEFT", "left_home")
    await robot.refresh("RIGHT", "tile_pose")
    destination = initial_tile_pose.value["destination"]
    await robot.move("RIGHT", "tile_source")
    await robot.grasp("RIGHT", "tile_gamma", observation=initial_tile_pose)
    await robot.move("RIGHT", destination)
    await robot.release("RIGHT", "tile_gamma", destination)
    await robot.move("RIGHT", "right_observe")
    # The lifecycle permission ended at first positive clearance.  Returning to
    # the released object is deliberately not a permanent-whitelist contact.
    await robot.move("LEFT", "fixture_ready")
