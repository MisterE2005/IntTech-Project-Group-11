from websockets.sync.client import connect
import json
from collections import defaultdict
import time
import threading
import pygame
import random

received_messages = []
cutscene_messages = []
receiver_teams = {}
team_a_roster = {}
team_b_roster = {}

cutscene_queue = []
cutscene_played = set()

plane_seen_times = defaultdict(dict)

PLANE_TIMEOUT = 30

# Sound placeholders (to be loaded later)
cutscene_sound = None
team_a_win_sound = None
team_b_win_sound = None
tie_sound = None

def assign_receiver_to_team(receiver_id):
    if receiver_id not in receiver_teams:
        if len(receiver_teams) % 2 == 0:
            receiver_teams[receiver_id] = 'A'
        else:
            receiver_teams[receiver_id] = 'B'
    return receiver_teams[receiver_id]

def handle_message(msg):
    current_time = time.time()

    if 'receiver' not in msg or 'address' not in msg or 'rssi' not in msg:
        return

    receiver = msg['receiver']
    plane_id = msg['address']
    rssi = msg['rssi']

    team = assign_receiver_to_team(receiver)
    plane_seen_times[plane_id][receiver] = current_time
    cutscene_messages.append(msg)

    # Check which teams currently see the plane
    receivers = plane_seen_times[plane_id].keys()
    teams_seen = {receiver_teams[r] for r in receivers if r in receiver_teams}

    if len(teams_seen) > 1 and plane_id not in cutscene_played:
        cutscene_queue.append(plane_id)
        cutscene_played.add(plane_id)
    # Determine best receiver (highest RSSI)
    best_receiver = None
    best_rssi = -999
    for r in plane_seen_times[plane_id]:
        for m in reversed(received_messages):
            if m.get("receiver") == r and m.get("address") == plane_id:
                if m["rssi"] > best_rssi:
                    best_rssi = m["rssi"]
                    best_receiver = r
                break

    if best_receiver is None:
        return  # No valid RSSI found

    best_team = receiver_teams[best_receiver]

    if best_team == 'A':
        team_a_roster[plane_id] = (best_receiver, rssi)
        team_b_roster.pop(plane_id, None)
    else:
        team_b_roster[plane_id] = (best_receiver, rssi)
        team_a_roster.pop(plane_id, None)

    cleanup_rosters(current_time)

    #Debug print
    print("---")
    print(f"Team A roster: {list(team_a_roster.keys())}")
    print(f"Team B roster: {list(team_b_roster.keys())}")

def cleanup_rosters(current_time):
    def remove_old_planes(roster):
        to_remove = []
        for plane_id in list(roster):
            last_seen_times = plane_seen_times.get(plane_id, {})
            if all((current_time - t > PLANE_TIMEOUT) for t in last_seen_times.values()):
                to_remove.append(plane_id)
        for plane_id in to_remove:
            roster.pop(plane_id, None)
            plane_seen_times.pop(plane_id, None)

    remove_old_planes(team_a_roster)
    remove_old_planes(team_b_roster)

def receive_data():
    max_msg = 50000  # Adjust as needed
    with connect("ws://192.87.172.71:1338") as websocket:
        count = 0
        while count < max_msg:
            msg = websocket.recv()
            try:
                msg = json.loads(msg)
                received_messages.append(msg)  # Store the raw JSON
                handle_message(msg)
            except json.JSONDecodeError:
                print("Failed to decode json, skipping...")
            except Exception as e:
                print("Error:", e)
                break
            # count += 1
        print("Received %d messages!" % count)

def play_cutscene(screen, plane_id):
    font_big = pygame.font.SysFont("Arial", 48, bold=True)
    font_med = pygame.font.SysFont("Arial", 32)
    font_small = pygame.font.SysFont("Arial", 24)
    if cutscene_sound:
        cutscene_sound.play()

    def load_image(name, scale=(500, 500)):
        img = pygame.image.load(name).convert_alpha()
        return pygame.transform.scale(img, scale)

    def draw_text_with_outline(surface, text, font, x, y, main_color, outline_color=(0, 0, 0), outline_thickness=2):
        for dx in [-outline_thickness, 0, outline_thickness]:
            for dy in [-outline_thickness, 0, outline_thickness]:
                if dx != 0 or dy != 0:
                    outline = font.render(text, True, outline_color)
                    surface.blit(outline, (x + dx, y + dy))
        rendered = font.render(text, True, main_color)
        surface.blit(rendered, (x, y))

    # Load all necessary images
    yellow_pose1 = load_image("yellow fight pose 1.png")
    yellow_pose2 = load_image("yellow fight pose 2.png")
    purple_pose1 = load_image("purple fight pose 1 (20250526103706).png")
    purple_pose2 = load_image("purple fight pose 2 (20250526103823).png")
    yellow_lose = load_image("yellow oose (20250526122019).png")
    purple_lose = load_image("purple loses (20250526115019).png")
    purple_punch = load_image("purple punch (20250526111040).png")
    yellow_punch = load_image("yelow punch (20250526120017).png")
    purple_charge = load_image("purple punch charge (20250526105925).png")
    yellow_charge = load_image("yellow pinch charge (20250526115535).png")
    background2 = pygame.image.load("B737_cockpit.jpg").convert_alpha()
    background2 = pygame.transform.scale(background2, (800, 600))

    # Determine which team won
    receivers = plane_seen_times.get(plane_id, {})

    best_rssi_a = -999
    best_rssi_b = -999

    for receiver_id in receivers:
        team = receiver_teams.get(receiver_id)
        if not team:
            continue

        rssi = None
        for msg in reversed(cutscene_messages):
            if msg.get("receiver") == receiver_id and msg.get("address") == plane_id:
                rssi = msg.get("rssi")
                break
        if rssi is None:
            continue
        if team == "A" and rssi > best_rssi_a:
            best_rssi_a = rssi
        elif team == "B" and rssi > best_rssi_b:
            best_rssi_b = rssi

    if cutscene_sound:
        cutscene_sound.play()

    if best_rssi_a > best_rssi_b:
        winner = "A"
        color = (70, 150, 255)
        if team_a_win_sound:
            team_a_win_sound.play()
    elif best_rssi_b > best_rssi_a:
        winner = "B"
        color = (255, 100, 100)
        if team_b_win_sound:
            team_b_win_sound.play()
    else:
        winner = "Tie"
        color = (255, 255, 0)
        if tie_sound:
            tie_sound.play()

    start_time = time.time()
    duration = 5.0
    clock = pygame.time.Clock()


    frame = 0
    pose_timer = 0
    pose_interval = 0.3

    while time.time() - start_time < duration:
        now = time.time()
        elapsed = now - start_time

        if now - pose_timer > pose_interval:
            frame = (frame + 1) % 2
            pose_timer = now

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()

        screen.blit(background2, (0, 0))

        # Set default flickering fight poses
        left_pose = yellow_pose1 if frame == 0 else yellow_pose2
        right_pose = purple_pose1 if frame == 0 else purple_pose2

        #win sequence in stages
        if winner != "Tie":
            if elapsed < 2.0:
                if winner == "A":
                    left_pose = yellow_charge
                    right_pose = purple_pose1 if frame == 0 else purple_pose2
                else:
                    left_pose = yellow_pose1 if frame == 0 else yellow_pose2
                    right_pose = purple_charge
            elif elapsed < 4.0:
                if bell_sound:
                    bell_sound.play()
                if winner == "A":
                    left_pose = yellow_punch
                    right_pose = purple_pose1 if frame == 0 else purple_pose2
                else:
                    left_pose = yellow_pose1 if frame == 0 else yellow_pose2
                    right_pose = purple_punch
                if punch_sound:
                    punch_sound.play()
            else:
                if winner == "A":
                    left_pose = yellow_punch
                    right_pose = purple_lose
                else:
                    left_pose = yellow_lose
                    right_pose = purple_punch

        screen.blit(left_pose, left_pose.get_rect(center=(200, 500)))
        screen.blit(right_pose, right_pose.get_rect(center=(675, 500)))

        # Draw text with outlines
        draw_text_with_outline(screen, "Signal Showdown!", font_big, 200, 100, color)
        draw_text_with_outline(screen, f"Plane {plane_id}", font_med, 300, 180, (255, 255, 255))
        draw_text_with_outline(screen, f"Receiver A RSSI: {best_rssi_a}", font_small, 220, 250, (70, 150, 255))
        draw_text_with_outline(screen, f"Receiver B RSSI: {best_rssi_b}", font_small, 220, 290, (255, 100, 100))

        if winner == "Tie":
            draw_text_with_outline(screen, "It's a tie!", font_med, 220, 360, (255, 255, 0))
        else:
            result_color = (70, 150, 255) if winner == "A" else (255, 100, 100)
            draw_text_with_outline(screen, f" {winner} wins!", font_med, 350, 360, result_color)

        draw_text_with_outline(screen, "The greater number has a better signal", font_small, 240, 400, (255, 255, 255))

        pygame.display.flip()
        pygame.time.delay(50)

# Optional: Store RSSI values for display
def get_roster_data():
    a_data = [(k, v[1]) for k, v in team_a_roster.items()]
    b_data = [(k, v[1]) for k, v in team_b_roster.items()]
    return a_data, b_data

def plot_teams_with_pygame():
    global cutscene_sound, bell_sound, punch_sound

    pygame.init()
    pygame.mixer.init()
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("Plane Roster Game")

    #Load sound effects
    try:
        cutscene_sound = pygame.mixer.Sound("Airplane Sound Effect.wav")
        bell_sound = pygame.mixer.Sound("Boxing Bell Sound Effect.wav")
        punch_sound = pygame.mixer.Sound("Punch Sound Effect.wav")

        pygame.mixer.music.load("Ending Theme (background music_).wav")
        pygame.mixer.music.set_volume(0.3)
        pygame.mixer.music.play(-1)

    except Exception as e:
        print("Sound loading error:", e)



    font = pygame.font.SysFont("Arial", 24)
    small_font = pygame.font.SysFont("Arial", 18)

    def draw_text_with_outline(surface, text, font, x, y, main_color, outline_color=(0, 0, 0), thickness=2):
        for dx in [-thickness, 0, thickness]:
            for dy in [-thickness, 0, thickness]:
                if dx != 0 or dy != 0:
                    outline = font.render(text, True, outline_color)
                    surface.blit(outline, (x + dx, y + dy))
        rendered = font.render(text, True, main_color)
        surface.blit(rendered, (x, y))

    bg_color = (30, 30, 30)
    team_a_color = (70, 150, 255)
    team_b_color = (255, 100, 100)
    clock = pygame.time.Clock()

    last_plane_count = 0

    team_a_data, team_b_data = get_roster_data()
    max_planes = len(team_a_data) + len(team_b_data)
    planes = []
    for _ in range(max_planes):
        plane = {
            "pos": [random.randint(0, 700), random.randint(0, 500)],
            "speed": [
                random.uniform(-3, 3),  # X speed
                random.uniform(-2, 2)  # Y speed
            ],
            "plane_id": f"FAKE{random.randint(1000, 9999)}"
        }
        planes.append(plane)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return

        # Get current team rosters
        team_a_data, team_b_data = get_roster_data()
        current_plane_count = len(team_a_data) + len(team_b_data)

        # If roster size changed, regenerate planes
        if current_plane_count != last_plane_count:
            last_plane_count = current_plane_count
            planes = []
            for i in range(current_plane_count):
                plane = {
                    "pos": [random.randint(0, 700), random.randint(0, 500)],
                    "speed": [
                        random.uniform(-1.5, 1.5),
                        random.uniform(-1.2, 1.2)
                    ],
                    "plane_id": f"FAKE{i:04d}"
                }
                planes.append(plane)

        screen.fill(bg_color)

        background1 = pygame.image.load("Aerial Skies (1).jpg").convert_alpha()
        # Load airplane sprite once
        airplane = pygame.image.load("plane.png").convert_alpha()
        airplane = pygame.transform.scale(airplane, (100, 100))

        # Create multiple planes

        background1 = pygame.transform.scale(background1, (800, 600))
        airplane = pygame.transform.scale(airplane, (100, 100))

        screen.blit(background1, (0, 0))

        for plane in planes:
            pos = plane["pos"]
            speed = plane["speed"]

            pos[0] += speed[0]
            pos[1] += speed[1]

            if pos[0] <= 0 or pos[0] >= screen.get_width() - airplane.get_width():
                speed[0] *= -1
            if pos[1] <= 0 or pos[1] >= screen.get_height() - airplane.get_height():
                speed[1] *= -1

            screen.blit(airplane, (int(pos[0]), int(pos[1])))

        # Scoreboards
        draw_text_with_outline(screen, f"Receiver A: {len(team_a_data)} planes", font, 20, 30, team_a_color)
        draw_text_with_outline(screen, f"Receiver B: {len(team_b_data)} planes", font, 600, 30, team_b_color)

        # Plane names in bottom corners
        for i, (plane_id, rssi) in enumerate(team_a_data):
            draw_text_with_outline(screen, plane_id, small_font, 20, 550 - i * 20, team_a_color)

        for i, (plane_id, rssi) in enumerate(team_b_data):
            draw_text_with_outline(screen, plane_id, small_font, 720, 550 - i * 20, team_b_color)

        if cutscene_queue:
            plane_id = cutscene_queue.pop(0)
            play_cutscene(screen, plane_id)

        keys = pygame.key.get_pressed()
        if keys[pygame.K_SPACE]:
            fake_plane_id = f"FAKE{random.randint(1000, 9999)}"
            # fake_receivers = ["receiverA", "receiverB"]
            fake_rssi_a = random.randint(-90, -30)
            fake_rssi_b = random.randint(-90, -30)

            # Assign receivers to teams manually
            receiver_teams["receiverA"] = "A"
            receiver_teams["receiverB"] = "B"

            # Save fake data into plane_seen_times and cutscene_messages
            now = time.time()
            plane_seen_times[fake_plane_id]["receiverA"] = now
            plane_seen_times[fake_plane_id]["receiverB"] = now

            cutscene_messages.append({
                "receiver": "receiverA",
                "address": fake_plane_id,
                "rssi": fake_rssi_a
            })
            cutscene_messages.append({
                "receiver": "receiverB",
                "address": fake_plane_id,
                "rssi": fake_rssi_b
            })

            # Trigger cutscene
            cutscene_queue.append(fake_plane_id)
            cutscene_played.add(fake_plane_id)

            # Pause briefly to prevent multiple triggers
            pygame.time.wait(500)
        pygame.display.flip()
        clock.tick(10)  # Update at 10 FPS

# Start receiving data in background thread
receiver_thread = threading.Thread(target=receive_data, daemon=True)
receiver_thread.start()

# Run pygame visualization in main thread
plot_teams_with_pygame()