import YanAPI

robot_ip = "10.30.89.75"
print(f"--- TESTING CONNECTION TO YANSHEE ROBOT AT {robot_ip} ---")

# Test 1: Class-based API
print("\n[TEST 1] Testing class-based API...")
try:
    robot = YanAPI.YanAPI(ip_address=robot_ip)
    
    print("Getting battery status...")
    battery = robot.get_battery()
    print(f"Battery: {battery}")
    
    print("Getting motions list...")
    list_motion = robot.get_motions_list()
    print("Motions list response:")
    print(list_motion)
except Exception as e:
    print(f"Class API error: {e}")

# Test 2: Module-level API (used by main_control2.py)
print("\n[TEST 2] Testing module-level API...")
try:
    YanAPI.set_robot_ip(robot_ip)
    YanAPI.init()
    
    print("Sending motion 'reset'...")
    res = YanAPI.sync_play_motion(name="reset")
    print(f"Reset response: {res}")
    
    print("Sending motion 'wave'...")
    res2 = YanAPI.sync_play_motion(name="wave")
    print(f"Wave response: {res2}")
except Exception as e:
    print(f"Module API error: {e}")