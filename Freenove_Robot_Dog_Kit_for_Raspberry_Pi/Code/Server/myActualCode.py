# Imports:

from Control import *
from Ultrasonic import *
import time

# Creating objects from imported classes
control = Control()
ultra = Ultrasonic()

# Debug variable
FULLDEBUG = True
MAINDEBUG = True

# Variable deciding how many turns it need to take to get 90 degrees
timesTurnToNinety = 26

# Function to check whether it's too close
def checkForSpace(dist):
    if ultra.get_distance() < dist:
        return False
    else:
        return True
    
def testNinetyDegrees():
    stop = False 
    counter = 0
    # Test to see how many 'control.turnLeft's it takes to spin 90 degrees
    while stop == False:
        keepgoing = input("Turn? y/n: ")
        if keepgoing.lower() == "y":
            control.turnLeft()
            counter += 1
            print(counter)
            time.sleep(1)
        elif keepgoing.lower() == "n":
            print(f"To turn 90 degrees, you need {counter} turnlefts")
            exit()

# Function to roam around avoiding obstacles
def roam():
    while True:
        while checkForSpace == False:
            for i in range(timesTurnToNinety/2):
                print("Turning Left")
                control.turnLeft()

        control.forWard()
    



testNinetyDegrees()
