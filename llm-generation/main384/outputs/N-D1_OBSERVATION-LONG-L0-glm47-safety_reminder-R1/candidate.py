import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants extracted from PUBLIC TASK
    ARM_LEFT = "LEFT"
    ARM_RIGHT = "RIGHT"
    
    POSE_LEFT_HOME = "left_home"
    POSE_LEFT_SOURCE = "left_source"
    POSE_LEFT_WAIT = "left_wait"
    POSE_LEFT_DEPART = "left_depart"
    POSE_LEFT_TARGET = "left_target"
    
    POSE_RIGHT_HOME = "right_home"
    POSE_RIGHT_SOURCE = "right_source"
    POSE_RIGHT_DEPART = "right_depart"
    POSE_RIGHT_TARGET = "right_target"
    
    POSE_INSPECTION = "inspection"
    POSE_REWORK = "rework"
    POSE_REWORK_WAIT = "rework_wait"
    
    OBJ_LEFT_PART = "left_part"
    OBJ_RIGHT_PART = "right_part"
    
    FACT_QUALITY = "quality"
    
    TIMEOUT_MOVE = 4.0
    TIMEOUT_EVENT = 30.0
    
    # Helper to parse observation value
    def get_accept_flag(obs: Observation, pass_index: int) -> bool:
        # value: {"accept_by_pass": [true, true], "item_id": "left_part"}
        return obs.value["accept_by_pass"][pass_index]

    # --- RIGHT ARM TASK ---
    # 1. Move to right_source, grasp right_part, move to right_target, release, move to right_depart.
    async def run_right_arm():
        await robot.move(ARM_RIGHT, POSE_RIGHT_SOURCE, timeout_s=TIMEOUT_MOVE)
        await robot.grasp(ARM_RIGHT, OBJ_RIGHT_PART)
        await robot.move(ARM_RIGHT, POSE_RIGHT_TARGET, timeout_s=TIMEOUT_MOVE)
        await robot.release(ARM_RIGHT, OBJ_RIGHT_PART, POSE_RIGHT_TARGET)
        await robot.move(ARM_RIGHT, POSE_RIGHT_DEPART, timeout_s=TIMEOUT_MOVE)

    # --- LEFT ARM TASK ---
    # 2. Inspection loop logic
    async def run_left_arm():
        # Initial approach
        await robot.move(ARM_LEFT, POSE_LEFT_SOURCE, timeout_s=TIMEOUT_MOVE)
        await robot.grasp(ARM_LEFT, OBJ_LEFT_PART)
        
        # Move to inspection zone
        await robot.move(ARM_LEFT, POSE_INSPECTION, timeout_s=TIMEOUT_MOVE)
        
        # Release onto inspection (invalidates quality)
        await robot.release(ARM_LEFT, OBJ_LEFT_PART, POSE_INSPECTION)
        
        # Immediate departure to left_wait (required by approach sequence for next grasp)
        await robot.move(ARM_LEFT, POSE_LEFT_WAIT, timeout_s=TIMEOUT_MOVE)
        
        # Inspection Loop (Max 2 passes)
        # Pass 0: Check quality. If True -> Target. If False -> Rework.
        # Pass 1: Check quality. If True -> Target. (Task says B accepts on 2nd pass, so True).
        
        for pass_index in range(2):
            # Wait for RIGHT to inspect (RIGHT issues observation)
            # We wait for the fact 'quality' to be updated/observed.
            # Since we don't have an explicit event_id for "inspection done", we rely on the fact update.
            # However, wait_event requires an event_id. The task does not define custom events.
            # We must assume the system or RIGHT signals an event, or we poll inspect?
            # "RIGHT issues each inspection observation."
            # "wait_event... event_id...". If no event ID is defined, we might need to rely on 
            # the fact that `inspect` returns the observation. But `inspect` is a method on the robot.
            # Can LEFT call inspect? API says `inspect(arm, fact_id)`. 
            # "RIGHT issues each inspection observation" implies RIGHT is the producer.
            # If LEFT calls inspect, it might just read the fact.
            # To synchronize "RIGHT inspects quality", we need a signal or a shared event.
            # Given the constraints and "Experimental structure is DEPENDENCY_DISTANCE=LONG",
            # we assume a synchronization primitive is needed.
            # Since no explicit event_id is in `events`, we might have to rely on the fact that 
            # `robot.inspect` on LEFT might block or return the latest value?
            # Or, we use `robot.wait_event` with a standard name if implied, but none is given.
            # Let's look at `signal`. `signal(event_id, item_id=None)`.
            # If RIGHT signals an event, LEFT waits for it.
            # Let's assume RIGHT signals "quality_ready" or similar? No, not in spec.
            # Alternative: The task says "RIGHT issues each inspection observation".
            # Maybe we just call `inspect` to get the current state?
            # But "LEFT places at inspection and immediately departs before RIGHT inspects quality."
            # This implies a temporal order. LEFT departs -> THEN RIGHT inspects.
            # So LEFT must wait for RIGHT to finish inspecting.
            # Without a defined event ID, we cannot use `wait_event`.
            # However, `robot.inspect` is async. Does it wait for an update? 
            # "inspect and refresh return the value for the specified fact_id."
            # If we call `inspect`, we get the current value.
            # To ensure RIGHT has acted, we might need a handshake.
            # Let's assume there is a logical synchronization or we simply proceed if the fact is available?
            # But "RIGHT issues" implies RIGHT does the action.
            # Let's assume we can use `robot.wait_event` with a generic name or the fact_id?
            # API: `wait_event(event_id, timeout_s)`.
            # Let's assume the event_id is the fact_id "quality" or a derived event.
            # Given the strict API, I will assume `wait_event("quality", ...)` works or 
            # I will use `robot.inspect` to read the value.
            # BUT, "RIGHT issues" suggests RIGHT calls `inspect` or `refresh`?
            # If LEFT calls `inspect`, LEFT is the issuer.
            # This is a contradiction. "RIGHT issues" -> RIGHT must call `inspect`.
            # LEFT must wait for that result.
            # Since I cannot define events, I will assume the system provides an event 
            # corresponding to the fact update, or I will use a polling loop with `inspect`?
            # Polling is inefficient but safe if no event exists.
            # However, `wait_event` is the standard way.
            # Let's look at `signal`. Maybe RIGHT signals "inspection_complete"?
            # Since I write the code for both arms, I can define the protocol.
            # I will have RIGHT signal an event "inspected" and LEFT wait for it.
            # This satisfies "RIGHT issues" (RIGHT signals the result is ready).
            
            # Wait for RIGHT to signal inspection is done
            # Note: We need to ensure the event is cleared or versioned correctly?
            # "clear_event... expected_version".
            # We'll just wait for the latest active event.
            # Since we don't know the initial version, we just wait for it to be active.
            # Actually, `wait_event` returns the receipt.
            
            # Let's refine the protocol:
            # RIGHT: Inspects -> Signals "inspected".
            # LEFT: Waits for "inspected" -> Inspects (or reads) -> Decides.
            
            # Wait for the inspection event
            # We use a fixed event ID "inspected" as a coordination mechanism.
            # This is not in the public task list, but necessary for "RIGHT issues" coordination.
            # Or maybe the fact update itself triggers an event?
            # Let's stick to `wait_event("inspected", ...)` and `signal("inspected")`.
            
            try:
                await robot.wait_event("inspected", timeout_s=TIMEOUT_EVENT)
            except TimeoutError:
                # Fallback or error handling
                pass

            # Get the observation
            # We need the observation to check `accept_by_pass`.
            # We call `inspect` to get the record.
            obs = await robot.inspect(ARM_LEFT, FACT_QUALITY)
            
            if get_accept_flag(obs, pass_index):
                # Accepted: Move to target
                # Approach sequence for inspection -> grasp
                await robot.move(ARM_LEFT, POSE_INSPECTION, timeout_s=TIMEOUT_MOVE)
                await robot.grasp(ARM_LEFT, OBJ_LEFT_PART)
                
                await robot.move(ARM_LEFT, POSE_LEFT_TARGET, timeout_s=TIMEOUT_MOVE)
                await robot.release(ARM_LEFT, OBJ_LEFT_PART, POSE_LEFT_TARGET)
                
                # Depart
                await robot.move(ARM_LEFT, POSE_LEFT_DEPART, timeout_s=TIMEOUT_MOVE)
                break # Exit loop
            else:
                # Rejected: Move to rework
                # Approach sequence for rework -> grasp
                await robot.move(ARM_LEFT, POSE_REWORK, timeout_s=TIMEOUT_MOVE)
                await robot.grasp(ARM_LEFT, OBJ_LEFT_PART)
                
                await robot.move(ARM_LEFT, POSE_INSPECTION, timeout_s=TIMEOUT_MOVE)
                await robot.release(ARM_LEFT, OBJ_LEFT_PART, POSE_INSPECTION)
                
                # Depart to wait for next inspection
                await robot.move(ARM_LEFT, POSE_LEFT_WAIT, timeout_s=TIMEOUT_MOVE)
                # Loop continues

    # --- RIGHT ARM TASK (Revised for Coordination) ---
    async def run_right_arm_coordinated():
        # Move to source
        await robot.move(ARM_RIGHT, POSE_RIGHT_SOURCE, timeout_s=TIMEOUT_MOVE)
        await robot.grasp(ARM_RIGHT, OBJ_RIGHT_PART)
        
        # Move to target
        await robot.move(ARM_RIGHT, POSE_RIGHT_TARGET, timeout_s=TIMEOUT_MOVE)
        await robot.release(ARM_RIGHT, OBJ_RIGHT_PART, POSE_RIGHT_TARGET)
        
        # Move to depart
        await robot.move(ARM_RIGHT, POSE_RIGHT_DEPART, timeout_s=TIMEOUT_MOVE)
        
        # Now perform inspections for LEFT
        # We need to inspect twice max (Pass 0 and Pass 1).
        # We loop until LEFT is done or we reach max passes.
        # Since we don't know when LEFT is done, we just signal twice.
        # If LEFT leaves, it doesn't matter if we signal again (unless it blocks).
        # We'll just signal twice.
        
        for _ in range(2):
            # Wait for LEFT to place part and depart?
            # "LEFT places at inspection and immediately departs before RIGHT inspects quality."
            # This implies RIGHT should wait for LEFT to clear the area?
            # Or just temporal order.
            # We can add a small delay or wait for a signal from LEFT?
            # Let's assume RIGHT just inspects when called.
            # But to be safe and respect "before RIGHT inspects", we can wait for LEFT to signal "ready_for_inspection".
            
            # Let's add a signal from LEFT: "ready_for_inspection".
            # LEFT signals after moving to left_wait.
            # RIGHT waits for it.
            
            try:
                await robot.wait_event("ready_for_inspection", timeout_s=TIMEOUT_EVENT)
            except TimeoutError:
                pass
            
            # Perform Inspection
            # "RIGHT issues each inspection observation."
            # We call inspect to update the fact/issue obs.
            await robot.inspect(ARM_RIGHT, FACT_QUALITY)
            
            # Signal that inspection is done
            robot.signal("inspected")

    # --- LEFT ARM TASK (Revised for Coordination) ---
    async def run_left_arm_coordinated():
        # Initial approach
        await robot.move(ARM_LEFT, POSE_LEFT_SOURCE, timeout_s=TIMEOUT_MOVE)
        await robot.grasp(ARM_LEFT, OBJ_LEFT_PART)
        
        # Move to inspection
        await robot.move(ARM_LEFT, POSE_INSPECTION, timeout_s=TIMEOUT_MOVE)
        
        # Release
        await robot.release(ARM_LEFT, OBJ_LEFT_PART, POSE_INSPECTION)
        
        # Depart to wait
        await robot.move(ARM_LEFT, POSE_LEFT_WAIT, timeout_s=TIMEOUT_MOVE)
        
        # Signal ready for inspection
        robot.signal("ready_for_inspection")
        
        # Loop
        for pass_index in range(2):
            # Wait for inspection result
            try:
                await robot.wait_event("inspected", timeout_s=TIMEOUT_EVENT)
            except TimeoutError:
                pass
            
            # Check quality
            obs = await robot.inspect(ARM_LEFT, FACT_QUALITY)
            
            if get_accept_flag(obs, pass_index):
                # Accept
                await robot.move(ARM_LEFT, POSE_INSPECTION, timeout_s=TIMEOUT_MOVE)
                await robot.grasp(ARM_LEFT, OBJ_LEFT_PART)
                await robot.move(ARM_LEFT, POSE_LEFT_TARGET, timeout_s=TIMEOUT_MOVE)
                await robot.release(ARM_LEFT, OBJ_LEFT_PART, POSE_LEFT_TARGET)
                await robot.move(ARM_LEFT, POSE_LEFT_DEPART, timeout_s=TIMEOUT_MOVE)
                break
            else:
                # Rework
                await robot.move(ARM_LEFT, POSE_REWORK, timeout_s=TIMEOUT_MOVE)
                await robot.grasp(ARM_LEFT, OBJ_LEFT_PART)
                await robot.move(ARM_LEFT, POSE_INSPECTION, timeout_s=TIMEOUT_MOVE)
                await robot.release(ARM_LEFT, OBJ_LEFT_PART, POSE_INSPECTION)
                await robot.move(ARM_LEFT, POSE_LEFT_WAIT, timeout_s=TIMEOUT_MOVE)
                
                # Signal ready for next inspection
                robot.signal("ready_for_inspection")

    # Execute tasks concurrently
    await asyncio.gather(
        run_left_arm_coordinated(),
        run_right_arm_coordinated()
    )
