#python 3 code
#Joanna, Hayden, and Philip
#fun message from Hayden
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
    LISTEN = enum.auto()
    ON_LINE = enum.auto()
    CORRECTING_RIGHT = enum.auto()
    CORRECTING_LEFT = enum.auto()


# Not a thread because this is the main thread which can be important for GUI access
class StateMachine():

    def __init__(self):
        # CONFIGURATION PARAMETERS
        self.IP_ADDRESS = "192.168.1.102" 	# SET THIS TO THE RASPBERRY PI's IP ADDRESS
        self.CONTROLLER_PORT = 5001
        self.TIMEOUT = 10					# If its unable to connect after 10 seconds, give up.  Want this to be a while so robot can init.
        self.STATE = States.LISTEN          # Our initial state is LISTEN
        self.RUNNING = True                 # We are running if our state machine is initialized
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
            sleep(0.05)
            if self.STATE == States.LISTEN:
                print("STATE: LISTEN")
                # pass
                self.STATE = States.ON_LINE
            if self.STATE == States.ON_LINE:
                # print("Left Sensor: {0}\t\tRight Sensor: {1}".format(self.sensors.left_sensor, self.sensors.right_sensor))
                with socketLock:
                    self.sock.sendall("a drive_straight(50)".encode())
                    self.sock.recv(128).decode()
                sleep(.05)

                # if line sensed on left
                if self.sensors.left_sensor < 1500:  # seen black tape
                    print("LEFT")
                    self.STATE = States.CORRECTING_LEFT

                # if line sensed on right
                if self.sensors.right_sensor < 1500:
                    print("RIGHT")
                    self.STATE = States.CORRECTING_RIGHT
            if self.STATE == States.CORRECTING_LEFT:
                # spin left
                with socketLock:
                    self.sock.sendall("a spin_left(75)".encode())
                    self.sock.recv(128).decode()
                sleep(0.05)

                # # then turn off and close connection
                # self.sock.sendall("c".  encode())
                # print(self.sock.recv(128).decode())
                
                # self.sock.close()
                self.STATE = States.ON_LINE

            if self.STATE == States.CORRECTING_RIGHT:
                # spin right
                with socketLock:
                    self.sock.sendall("a spin_right(75)".encode())
                    self.sock.recv(128).decode()
                sleep(0.05)

                self.STATE = States.ON_LINE
        # END OF CONTROL LOOP

        # First stop any other threads talking to the robot
        self.sensors.RUNNING = False
        self.sensors.join()

        print("################## Setting speed to zero ##################")
        with socketLock:
            self.sock.sendall("a drive_straight(0)".encode())
            print(self.sock.recv(128).decode())

        print("################## Attempting to disconnect ##################")
        # Need to disconnect
        # The c command stops the robot and disconnects.  The stop command will also reset the Create's mode to a battery safe PASSIVE.  It is very important to use this command!
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
            print("################## [ESC] -- STOP EVERYTHING NOW! ##################")
            return False

# END OF STATEMACHINE


class Sensing(threading.Thread):
    def __init__(self, socket):
        threading.Thread.__init__(self)   # MUST call this to make sure we setup the thread correctly
        self.RUNNING = True
        self.sock = socket
        self.left_sensor = 0
        self.right_sensor = 0
        self.left_encoder = 0
        self.right_encoder = 0

    def run(self):
        while self.RUNNING:
            sleep(0.2)
            # Sense
            with socketLock: # !IMPORTANT: Threadsafe-ness
                self.sock.sendall("a cliff_front_left_signal".encode())
                self.left_sensor = int(self.sock.recv(128).decode())
                self.sock.sendall("a cliff_front_right_signal".encode())
                self.right_sensor = int(self.sock.recv(128).decode())
                self.sock.sendall("a left_encoder_counts".encode())
                self.left_encoder = int(self.sock.recv(128).decode())
                self.sock.sendall("a right_encoder_counts".encode())
                self.right_encoder = int(self.sock.recv(128).decode())              

            print("Cliff Front --\tLeft: ", self.left_sensor, "\t|\tRight: ", self.right_sensor)
            print("Encoders --\tLeft: ", self.left_encoder, "\t|\ttRight: ", self.right_encoder)
            # Delay to be sure
            # sleep(0.01);

            # with socketLock: # !IMPORTANT: Threadsafe-ness
            #     self.sock.sendall("a light_bump_front_left_signal".encode())
            #     self.left_sensor = int(self.sock.recv(128).decode())

# END OF SENSING

if __name__ == "__main__":
    sm = StateMachine()
    sm.main()
