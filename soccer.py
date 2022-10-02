import pgzero, pgzrun, pygame
import math, sys, random
from enum import Enum
from pygame.math import Vector2

WIDTH = 800
HEIGHT = 480
TITLE = "Football Game"

HALF_WINDOW_W = WIDTH / 2

LEVEL_W = 1000
LEVEL_H = 1400
HALF_LEVEL_W = LEVEL_W // 2
HALF_LEVEL_H = LEVEL_H // 2

HALF_PITCH_W = 460
HALF_PITCH_H = 650

GOAL_WIDTH = 186
GOAL_DEPTH = 20
HALF_GOAL_W = GOAL_WIDTH // 2

PITCH_BOUNDS_X = (HALF_LEVEL_W - HALF_PITCH_W, HALF_LEVEL_W + HALF_PITCH_W)
PITCH_BOUNDS_Y = (HALF_LEVEL_H - HALF_PITCH_H, HALF_LEVEL_H + HALF_PITCH_H)

GOAL_BOUNDS_X = (HALF_LEVEL_W - HALF_GOAL_W, HALF_LEVEL_W + HALF_GOAL_W)
GOAL_BOUNDS_Y = (HALF_LEVEL_H - HALF_PITCH_H - GOAL_DEPTH,
                 HALF_LEVEL_H + HALF_PITCH_H + GOAL_DEPTH)

PITCH_RECT = pygame.rect.Rect(PITCH_BOUNDS_X[0], PITCH_BOUNDS_Y[0], HALF_PITCH_W * 2, HALF_PITCH_H * 2)
GOAL_0_RECT = pygame.rect.Rect(GOAL_BOUNDS_X[0], GOAL_BOUNDS_Y[0], GOAL_WIDTH, GOAL_DEPTH)
GOAL_1_RECT = pygame.rect.Rect(GOAL_BOUNDS_X[0], GOAL_BOUNDS_Y[1] - GOAL_DEPTH, GOAL_WIDTH, GOAL_DEPTH)

PLAYER_START_POS = [(350, 550)]

DRIBBLE_DIST_X, DRIBBLE_DIST_Y = 18, 16

PLAYER_SPEED = 2

def sin(x):
    return math.sin(x*math.pi/4)

def cos(x):
    return sin(x+2)

def vec_to_angle(vec):
    return int(4 * math.atan2(vec.x, -vec.y) / math.pi + 8.5) % 8

def angle_to_vec(angle):
    return Vector2(sin(angle), -cos(angle))

def dist_key(pos):
    return lambda p: (p.vpos - pos).length()

def safe_normalise(vec):
    length = vec.length()
    if length == 0:
        return Vector2(0,0), 0
    else:
        return vec.normalize(), length

class MyActor(Actor):
    def __init__(self, img, x=0, y=0, anchor=None):
        super().__init__(img, (0, 0), anchor=anchor)
        self.vpos = Vector2(x, y)

    def draw(self, offset_x, offset_y):
        self.pos = (self.vpos.x - offset_x, self.vpos.y - offset_y) # Dùng để scrolling
        super().draw()

KICK_STRENGTH = 11.5
DRAG = 0.98


def ball_physics(pos, vel, bounds):
    pos += vel

    if pos < bounds[0] or pos > bounds[1]:
        pos, vel = pos - vel, -vel

    return pos, vel * DRAG


class Goal(MyActor):
    def __init__(self, team):
        x = HALF_LEVEL_W
        y = 0 if team == 0 else LEVEL_H
        super().__init__("goal" + str(team), x, y)

        self.team = team

def avg(a, b):
    return b if abs(b-a) < 1 else (a+b)/2

def on_pitch(x, y):
    return PITCH_RECT.collidepoint(x,y) \
           or GOAL_0_RECT.collidepoint(x,y) \
           or GOAL_1_RECT.collidepoint(x,y)

class Ball(MyActor):
    def __init__(self):
        super().__init__("ball", HALF_LEVEL_W, HALF_LEVEL_H)

        self.vel = Vector2(0, 0)

        self.owner = None
        self.timer = 0

    def collide(self, p):
        return p.timer < 0 and (p.vpos - self.vpos).length() <= DRIBBLE_DIST_X

    def update(self):
        self.timer -= 1

        if self.owner:
            new_x = avg(self.vpos.x, self.owner.vpos.x + DRIBBLE_DIST_X * sin(self.owner.dir))
            new_y = avg(self.vpos.y, self.owner.vpos.y - DRIBBLE_DIST_Y * cos(self.owner.dir))

            if on_pitch(new_x, new_y):
                self.vpos = Vector2(new_x, new_y)
            else:
                self.owner.timer = 60
                self.vel = angle_to_vec(self.owner.dir) * 3
                self.owner = None
        else:
            if abs(self.vpos.y - HALF_LEVEL_H) > HALF_PITCH_H:
                bounds_x = GOAL_BOUNDS_X
            else:
                bounds_x = PITCH_BOUNDS_X

            if abs(self.vpos.x - HALF_LEVEL_W) < HALF_GOAL_W:
                bounds_y = GOAL_BOUNDS_Y
            else:
                bounds_y = PITCH_BOUNDS_Y

            self.vpos.x, self.vel.x = ball_physics(self.vpos.x, self.vel.x, bounds_x)
            self.vpos.y, self.vel.y = ball_physics(self.vpos.y, self.vel.y, bounds_y)

        for target in game.players:
            if (not self.owner or self.owner.team != target.team) and self.collide(target):
                if self.owner:
                    self.owner.timer = 60
                game.teams[target.team].active_control_player = self.owner = target

        if self.owner:
            team = game.teams[self.owner.team]
            target = None
            
            do_shoot = team.controls.shoot()
                
            if do_shoot:

                vec = angle_to_vec(self.owner.dir)

                self.owner.timer = 10 

                self.vel = vec * KICK_STRENGTH

                self.owner = None

def allow_movement(x, y):
    if abs(x - HALF_LEVEL_W) > HALF_LEVEL_W:
        return False

    elif abs(x - HALF_LEVEL_W) < HALF_GOAL_W + 20:
        return abs(y - HALF_LEVEL_H) < HALF_PITCH_H

    else:
        return abs(y - HALF_LEVEL_H) < HALF_LEVEL_H

class Player(MyActor):
    ANCHOR = (25,37)

    def __init__(self, x, y, team):
        kickoff_y = (y / 2) + 550 - (team * 400)

        super().__init__("blank", x, kickoff_y, Player.ANCHOR)

        self.home = Vector2(x, y)

        self.team = team
        
        self.dir = 0

        self.anim_frame = -1

        self.timer = 0

    def update(self):
        self.timer -= 1
        target = Vector2(0,0)
        speed = PLAYER_SPEED

        my_team = game.teams[self.team]
        pre_kickoff = game.kickoff_player != None
        ball = game.ball

        if not pre_kickoff:
            target = self.vpos + my_team.controls.move(PLAYER_SPEED)
        else:
            target = Vector2(ball.vpos)    
            vel = Vector2(ball.vel)         
            frame = 0
            while (target - self.vpos).length() > PLAYER_SPEED * frame + DRIBBLE_DIST_X and vel.length() > 0.5:
                target += vel
                vel *= DRAG
                frame += 1

        vec, distance = safe_normalise(target - self.vpos)


        if distance > 0:
        
            distance = min(distance, PLAYER_SPEED)
            target_dir = vec_to_angle(vec)
            
            if allow_movement(self.vpos.x + vec.x * distance, self.vpos.y):
                self.vpos.x += vec.x * distance
            if allow_movement(self.vpos.x, self.vpos.y + vec.y * distance):
                self.vpos.y += vec.y * distance

            self.anim_frame = (self.anim_frame + max(distance, 1.5)) % 72
        else:
            target_dir = vec_to_angle(ball.vpos - self.vpos)
            self.anim_frame = -1
            
        dir_diff = (target_dir - self.dir)
        self.dir = (self.dir + [0, 1, 1, 1, 1, 7, 7, 7][dir_diff % 8]) % 8

        suffix = str(self.dir) + str((int(self.anim_frame) // 18) + 1)
        self.image = "player" + str(self.team) + suffix


class Team:
    def __init__(self, controls):
        self.controls = controls
        self.active_control_player = None
        self.score = 0

    def human(self):
        return self.controls != None


class Game:
    def __init__(self, p1_controls=None, p2_controls=None):
        self.teams = [Team(p1_controls), Team(p2_controls)]
        
        self.scoring_team = 1

        self.reset()

    def reset(self):
        self.players = []
        
        for pos in PLAYER_START_POS:
            self.players.append(Player(LEVEL_W // 2, LEVEL_H // 2, 0))
            self.players.append(Player(LEVEL_W // 2, LEVEL_H // 2, 1))

        self.goals = [Goal(i) for i in range(2)]

        self.teams[0].active_control_player = self.players[0]
        self.teams[1].active_control_player = self.players[1]

        other_team = 1 if self.scoring_team == 0 else 0

        self.kickoff_player = self.players[other_team]
        self.kickoff_player.vpos = Vector2(HALF_LEVEL_W - 30 + other_team * 60, HALF_LEVEL_H)

        self.ball = Ball()

        self.camera_focus = Vector2(self.ball.vpos)

    def update(self):
        if abs(self.ball.vpos.y - HALF_LEVEL_H) > HALF_PITCH_H:

            self.scoring_team = 0 if self.ball.vpos.y < HALF_LEVEL_H else 1
            self.teams[self.scoring_team].score += 1

        if self.ball.owner:
            o = self.ball.owner
            pos, team = o.vpos, o.team
            owners_target_goal = game.goals[team]
            other_team = 1 if team == 0 else 0

            self.kickoff_player = None

        for obj in self.players + [self.ball]:
            obj.update()

        camera_ball_vec, distance = safe_normalise(self.camera_focus - self.ball.vpos)
        if distance > 0:
            self.camera_focus -= camera_ball_vec * min(distance, 8)

    def draw(self):
        offset_x = max(0, min(LEVEL_W - WIDTH, self.camera_focus.x - WIDTH / 2))
        offset_y = max(0, min(LEVEL_H - HEIGHT, self.camera_focus.y - HEIGHT / 2))
        offset = Vector2(offset_x, offset_y)

        screen.blit("pitch", (-offset_x, -offset_y)) #Scrolling

        objects = sorted([self.ball] + self.players, key = lambda obj: obj.y)
        objects = [self.goals[0]] + objects + [self.goals[1]]

        for obj in objects:
            obj.draw(offset_x, offset_y)

key_status = {}

def key_just_pressed(key):
    result = False

    prev_status = key_status.get(key, False)

    if not prev_status and keyboard[key]:
        result = True

    key_status[key] = keyboard[key]

    return result

class Controls:
    def __init__(self, player_num):
        if player_num == 0:
            self.key_up = keys.UP
            self.key_down = keys.DOWN
            self.key_left = keys.LEFT
            self.key_right = keys.RIGHT
            self.key_shoot = keys.SPACE
        else:
            self.key_up = keys.W
            self.key_down = keys.S
            self.key_left = keys.A
            self.key_right = keys.D
            self.key_shoot = keys.LSHIFT

    def move(self, speed):
        dx, dy = 0, 0
        if keyboard[self.key_left]:
            dx = -1
        elif keyboard[self.key_right]:
            dx = 1
        if keyboard[self.key_up]:
            dy = -1
        elif keyboard[self.key_down]:
            dy = 1
        return Vector2(dx, dy) * speed

    def shoot(self):
        return key_just_pressed(self.key_shoot)

def update():
    game.update()
    
def draw():
    game.draw()
    screen.draw.text("Red Team", (10, 10), color=(255, 0, 0))
    screen.draw.text("Blue Team", (10, HEIGHT-30), color=(0, 0, 255))
    screen.draw.text(str(game.teams[0].score), (HALF_WINDOW_W , 10), color=(0, 0, 255))
    screen.draw.text(str(game.teams[1].score), (HALF_WINDOW_W - 40, 10), color=(255, 0, 0))
            
game = Game(Controls(0), Controls(1))

pgzrun.go()
