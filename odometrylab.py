#python 3 code
import socket
from time import *
from pynput import keyboard
"""pynput: On Mac OSX, one of the following must be true:
* The process must run as root. OR
* Your application must be white listed under Enable access for assistive devices. Note that this might require that you package your application, since otherwise the entire Python installation must be white listed."""
import sys
import threading
import enum

socketLock = threading.Lock()

# You should fill this in with your states
class States(enum.Enum):
    DRIVE_FORWARD   = enum.auto()
    TURN_RIGHT      = enum.auto()
    TURN_LEFT       = enum.auto()

# Not a thread because this is the main thread which can be important for GUI access
class StateMachine():

    def __init__(self):
        # CONFIGURATION PARAMETERS
        self.IP_ADDRESS = "192.168.1.102" 	# SET THIS TO THE RASPBERRY PI's IP ADDRESS
        self.CONTROLLER_PORT = 5001
        self.TIMEOUT = 10					# If its unable to connect after 10 seconds, give up.  Want this to be a while so robot can init.
        self.STATE = States.DRIVE_FORWARD
        self.RUNNING = True
        self.DIST = False

        # connect to the motorcontroller
        try:
            with socketLock:
                self.sock = socket.create_connection( (self.IP_ADDRESS, self.CONTROLLER_PORT), self.TIMEOUT)
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            print("Connected to RP")
        except Exception as e:
            print("ERROR with socket connection", e)
            sys.exit(0)

        # Collect events until released
        self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.listener.start()

    def main(self):
        # connect to the robot
        """ The i command will initialize the robot.  It enters the create into FULL mode which means it can drive off tables and over steps: be careful!"""
        with socketLock:
            self.sock.sendall("i /dev/ttyUSB0".encode())
            print("Sent command")
            result = self.sock.recv(128)
            print(result)
            if result.decode() != "i /dev/ttyUSB0":
                self.RUNNING = False

        self.sensors = Sensing(self.sock)
        # Start getting data
        self.sensors.start()

        # BEGINNING OF THE CONTROL LOOP
        while(self.RUNNING):
            sleep(0.1)
            if self.STATE == States.DRIVE_FORWARD:
                # drive forward
                with socketLock:
                    self.sock.sendall("a drive_straight(50)".encode())
                    discard = self.sock.recv(128).decode()
                sleep(.05)

                # # if line sensed on left
                if self.sensors.left_sensor < 1900:  # seen black tape
                    print("LEFT")
                    # self.STATE = States.TURN_LEFT

                # #if line sensed on right
                if self.sensors.right_sensor < 1750:
                    print("RIGHT")
                    # self.STATE = States.TURN_RIGHT
            elif self.STATE == States.TURN_RIGHT:
                pass
            elif self.STATE == States.TURN_LEFT: 
                pass


        # END OF CONTROL LOOP

        # First stop any other threads talking to the robot
        self.sensors.RUNNING = False
        self.sensors.join()

        # Need to disconnect
        """ The c command stops the robot and disconnects.  The stop command will also reset the Create's mode to a battery safe PASSIVE.  It is very important to use this command!"""
        with socketLock:
            self.sock.sendall("c".encode())
            print(self.sock.recv(128))

        with socketLock:
            self.sock.close()
        # If the user didn't request to halt, we should stop listening anyways
        self.listener.stop()

    def on_press(self, key):
        # WARNING: DO NOT attempt to use the socket directly from here
        try:
            print('alphanumeric key {0} pressed'.format(key.char))
            if key.char == 'd':
                self.DIST = True
        except AttributeError:
            print('special key {0} pressed'.format(key))

    def on_release(self, key):
        # WARNING: DO NOT attempt to use the socket directly from here
        print('{0} released'.format(key))
        if key == keyboard.Key.esc or key == keyboard.Key.ctrl:
            # Stop listener
            self.RUNNING = False
            return False

# END OF STATEMACHINE


class Sensing(threading.Thread):
    def __init__(self, socket):
        threading.Thread.__init__(self)   # MUST call this to make sure we setup the thread correctly
        self.RUNNING = True
        self.sock = socket

    def run(self):
        while self.RUNNING:
            sleep(0.1)

        with socketLock:
            self.sock.sendall("a cliff_front_left_signal".encode())
            self.left_sensor = int(self.sock.recv(128).decode())
            self.sock.sendall("a cliff_front_right_signal".encode())
            self.right_sensor = int(self.sock.recv(128).decode())
        print("Cliff Front --\tLeft: ", self.left_sensor, "\t|\tRight: ", self.right_sensor)
            
            # This is where I would get a sensor update
            # Store it in this class
            # You can change the polling frequency to optimize performance, don't forget to use socketLock


# END OF SENSING


if __name__ == "__main__":
    sm = StateMachine()
    sm.main()
