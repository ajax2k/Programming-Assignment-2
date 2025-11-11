'''

    Programming Assignment 2: Distance Vector Routing Protocols
        Description:
        The protocol runs on top of four servers using UDP. Each server reads information
        from a topology file and exchanges routing updates with its neighbors
            - parses topology file which contains servers, ports and link costs
            - creates UDP socket for sending/recieving messages
            - uses bellman-ford algorithm for updating routing tables
            - user commands:  update, step, display, disable, crash, and exit
            - sends routing updates (every few seconds)

'''
import socket # for socket programming
import argparse
import json
import threading
import time
# 
INF = 1000000000

'''

    Command: def p_args():
        Handles the command line arguments used to start the distance vector server.
        Able to read topology file and update interval from command line

        Usage Example:
            python3 dv.py -t <filename> -i 2

'''
def p_args():
    # handles command line
    ap = argparse.ArgumentParser()
    # required for topology file
    ap.add_argument('-t','--topology', required=True)
    # required for updates
    ap.add_argument('-i','--interval', type=int, required=True)

    return ap.parse_args()
'''

    Command: def read_top(): 
        Reads and processes the topology file
    
    To Do:
    - open topology file given 'path'
    - read each line and split data (ignore blanks/comments)
    - get number of servers/neighbors from first 2 lines
    - store each server ID, IP & port in a dictionary
    - store the remaining lines in a list (rc)
    - return both the dictionary & rc list

'''
def read_top(path):
    pass

'''

    Command: def state(): 
        Sets up information for the distance vector server. Depends on servers, rc and interval
        in order to create the socket, neighbors, routing table and state data

'''
def state(servers, rc, interval):
    # user server ID (lowest)
    user = sorted(servers.keys())[0]
    my_ip, my_port = servers[user]
    # dictionary for neighbors and cost
    neighbors = {}
    for row in rc:
        s1, s2, c  = row
        s1, s2  = int(s1), int(s2)
        # if cost is infinity - set to INF
        if c.lower() == 'inf':
            cost = INF 
        else:
            cost = int(c)
        # check which link is 'user' - other is neighbor
        if s1 == user:
            neighbors[s2] = cost
        elif s2 == user:
            neighbors[s1] = cost
    # routing table for servers
    rt = {}
    for srv_id in servers:
        # user has 0 cost
        if srv_id == user:
            rt[srv_id] = (user, 0)
        # neighbor use thier cost
        elif srv_id in neighbors:
            rt[srv_id] = (srv_id, neighbors[srv_id])
        # all others set to INF 
        else:
            rt[srv_id] = (-1, INF)
    # UDP socket for sending/receiving
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((my_ip, my_port))
    sock.settimeout(1.0)
    # track when neighbor heard from last
    last = {n: time.time() for n in neighbors}
    # state dictionary
    state = {
        'servers' : servers,
        'neighbors' : neighbors,
        'rt' : rt,
        'pkts' : 0,
        'last' : last,
        'user' : user,
        'my_ip': my_ip,
        'my_port' : my_port,
        'interval' : int(interval),
        'sock' : sock,
        'stop' : threading.Event(),

    }
    
    return state
'''

    Command: def rx():
        Receive incoming UDP packets.

    To Do:
        - wait for incoming data from UDP socket
        - decode and aprse the packet (json)
        - identify which server sent
        - update the 'last' heard time from sender
        - call bell_ford() to apply distance vector updates


'''
def rx(state):
    pass

''''

    Command: def tx():
        Handles periodic updates and neighbor checks

    To Do:
        - repeatedly call snd_update to send routing info
        - call dead_neigh() to mark inactive neighbor
        - sleep for interval set in state before looping again

'''
def tx(state):
    pass

'''

    Command: bell_ford():
        Bellman-Ford algorithm for distance vector updates

    To Do:
        - compare known costs to possible paths through neighbor
        - cheaper route found = update routing table
        - runs every time new data is received from neighbor

'''
def bell_ford():
    pass

'''

    Command: def data_pckt():
        Builds the routing update packet

    To Do:
        - create dictionary that includes: user server ID, my_ip, my_port, routing
            tbale (destination/cost)
        - cnvert to json for sending with UDP

'''
def data_pckt(state):
    pass

'''

    Command: def snd_update():
        Sends routing updates to all neighbors

    To Do:
        - build the update packet using data_pckt()
        - send to each active neighor using IP & port

'''
def snd_update(state):
    pass

'''

    Command: def dead_neigh():
        Detects and handles dead neighbors

    To Do:
        - check when neighbor last sent update
        - no message received for 3 intervals - mark as INF
        - update the routing table

'''
def dead_neigh(state):
    pass

''''

    Command: def update():
        Changes the cost of a link between two servers

    To Do:
        - take two server IDs and a new cost from user
        - update the cost in neighbors & routing table
        - print 

'''
def update():
    pass

'''

Command: def step():
    manually triggers an update message

To Do:
    - call snd_update() 
    - print 

'''
def step(state):
    pass

'''

Command: def pckts():
    Depends on state and demonstrates how many incoming packets have been received.
    Prints the number of packets and resets the counter.

'''
def pckts(state):
    # print number of packets received
    print('Packets: ',state['pkts'])
    # reset count 0
    state['pkts'] = 0
    print('Packets Secured.')

'''

    Command: def display():
        Displays the current routing table

    To Do:
        - print each destination, hop & cost from routing table
        - sort output by destination ID
        - print

'''
def display(state):
    pass

'''

    Command: def disable():
        Disables a link to a neighbor

    To Do:
        - take a neighbor ID as input
        - set that neigbors cost to INF in table
        - update routing table (disconnection)
        - print

'''
def disable():
    pass

'''

    Command: def crash():
        Server crash, closing all active links in program


'''
def crash(state):
    # go through all neighbors and mark as INF
    for s in list(state['neighbors'].keys()):
        state['neighbors'][s] = INF
        state['rt'][s] = (-1, INF)
    
    print('Bye!')

'''

    Command: def cmnds():
        Handles all user commands entered during execution

    To Do:
        - continuously wait for user input
        - read the command, split into parts & match to function
        - handle: update, step, pckts, display, disable, crash & exit
        - call proper function for each command
        - loop until user exits program
'''
def cmnds(state):
    pass

'''

    Main: def main():
        executes the program to test the distance vector algorithm and UDP connections

    To Do:
        - use read_top to load topology file 
        - create main state dictionary (call state())
        - start rx/tx thread for sending/receiving
        - call cmnds to begin loop
        - stop all thread & close socket when user exits

'''
def main():
    args = p_args()


    main()
