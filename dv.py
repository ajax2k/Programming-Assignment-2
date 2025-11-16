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
num_servers = 0
num_neighbors = 0
servers = {} # server_ID :(ip,port)  
rc = []
interval = 0

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
        
    Returns:
        servers: dictionary of server_ID : (ip,port)
        rc: list of remaining connections (server1, server2, cost)

'''
def read_top(path):
    path = "./" + path
    
    try:
        with open(path,'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print('File not found:',path)
        return
        
    # remove blank lines/comments
    data = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#'):
            data.append(line)

    # assign variables
    num_servers = int(data[0])
    num_neighbors = int(data[1])
    
    # assign server dictionary
    for i in range(2, 2 + num_servers):
        line = data[i].split()
        srv_id = int(line[0])
        ip = line[1]
        port = int(line[2])
        
        servers.update({srv_id:(ip,port)})
        
    # assign remaining lines to rc
    for j in range(2 + num_servers, 2 + num_servers + num_neighbors):
        line = data[j].split()
        rc.append(line)
        
    return servers, rc
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
            rt[srv_id] = (srv_id, 0)
        # neighbor use their cost
        elif srv_id in neighbors:
            rt[srv_id] = (srv_id ,neighbors[srv_id])
        # all others set to INF 
        else:
            rt[srv_id] = INF
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
        'lock' : threading.Lock()
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
    while not state['stop'].is_set():
        try:
            # wait for incoming data
            data, addr = state['sock'].recvfrom(4096)
            # decode and parse the packet
            packet = json.loads(data.decode('utf-8'))

            # identify which server sent the packet + info about neighbors
            from_server = packet['user']
            neighbor_vector = packet['rt']

            # update the 'last' heard time from sender
            with state['lock']:
                state['pkts'] += 1
                if from_server in state['neighbors']:
                    state['last'][from_server] = time.time()
            # call bell_ford() to apply distance vector updates
            bell_ford(state, from_server, neighbor_vector)
        except socket.timeout:
            continue
        except Exception as e:
            print(f"Error receiving packet: {e}")

''''

    Command: def tx():
        Handles periodic updates and neighbor checks

    To Do:
        - repeatedly call snd_update to send routing info
        - call dead_neigh() to mark inactive neighbor
        - sleep for interval set in state before looping again

'''
def tx(state):
    # continuously listen for incoming packets
    while not state['stop'].is_set():
        # wait for incoming data
        snd_update(state)
        # Check for dead neighbors
        dead_neigh(state)
        # Sleep for the specified interval before sending the next update
        # has 0.2 second minimum to prevent misinput from user commands
        time.sleep(max(0.2, state['interval']))

'''

    Command: bell_ford():
        uses Bellman-Ford algorithm for distance vector updates, compares known cost to destination 
        and cost through a neighbor (sender). If new path is less, table is updated.

'''
def bell_ford(state, snd, snd_rt):
   # cost from user to sender
   with state['lock']:
    hop, c2s = state['rt'].get(snd, (-1, INF))

    # check destination (sender) knows
    for dstr, sndc in snd_rt.items():
        # convert json to int
        d = int(dstr)
        sndc = int(sndc)

        # new cost from sender
        if c2s == INF or sndc == INF:
            new = INF
        else: 
            new = c2s + sndc
        # current cost -> table
        curr = state['rt'].get(d, (-1, INF))

        # update if path is less
        if  new < curr:
            state['rt'][d] = (snd, new)


'''

    Command: def data_pckt():
        Builds the routing update packet

    To Do:
        - create dictionary that includes: user server ID, my_ip, my_port, routing
            tbale (destination/cost)
        - cnvert to json for sending with UDP

'''
def data_pckt(state):
    with state ['lock']:
        rt_cost = {server_id: cost for server_id, (hop, cost) in state['rt'].items()}
    packet = {
        'user' : state['user'],
        'my_ip' : state['my_ip'],
        'my_port' : state['my_port'],
        'rt' : rt_cost
    }
    return json.dumps(packet).encode('utf-8')

'''

    Command: def snd_update():
        Sends routing updates to all neighbors, uses data_pckt to build packet and send it 
        through UDP socket.

'''
def snd_update(state):
    # build packet
    pckt = data_pckt(state)
    # go through each neighbor
    for n_id in state['neighbors'].keys():
        # get neighbor IP and Port
        ip, port = state['servers'][n_id]
        # send update packet to neighbor
        try:
            state['sock'].sendto(pckt,(ip, port))
        # ignore send error (stops program from crashing)
        except Exception:
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
    # get current time
    now = time.time()
    with state['lock']:
        # calculate max interval for inactivity
        max_interval = state['interval'] * 3
        # loop through neighbors and check last heard time
        for neighbor_id in list(state['neighbors'].keys()):
            # check last heard time for neighbor
            last_time = state['last'].get(neighbor_id, 0)
            # if no message received for 3 intervals, mark as INF
            if now - last_time > max_interval:
                print(f"Neighbor {neighbor_id} is inactive. Marking as INF.")
                state['neighbors'][neighbor_id] = INF
                # update routing table for this neighbor
                state['rt'][neighbor_id] = (neighbor_id, INF)
                # if neighbor is marked as INF, update routing 
                # table for all destinations that use this neighbor as hop
                for dest_id, (hop, cost) in state['rt'].items():
                    if hop == neighbor_id:
                        state['rt'][dest_id] = (-1, INF)
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

'''
def step(state):
    print('Sending routing update...')
    snd_update(state)
    print('Update sent.')

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
    with state['lock']:
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

def help():
    print("\nAvailable commands:")
    print(" update <server1> <server2> <cost> - Update the cost of a link between two servers")
    print(" step                              - Send routing update")
    print(" pckts                             - Display the number of packets")
    print(" display                           - Display the current routing table")
    print(" disable <neighbor_id>             - Disable a link to a neighbor")
    print(" crash                             - Simulate a server crash")
    print(" exit                              - Exit the program")

def cmnds(state):
    print("\nStarted Vector Routing Server.")
    print(f"Server ID: {state['user']}")
    print(f"Listening on IP: {state['my_ip']}:{state['my_port']}")
    print("Type 'help' for a list of available commands.\n")      
    while not state['stop'].is_set():
        try:
            cmd = input("> ").strip().split()
            if not cmd:
                continue
            command = cmd[0].lower()
            if command == 'help':
                help()
            elif command == 'update' and len(cmd) == 4:
                update()
            elif command == 'step':
                step(state)
            elif command == 'pckts':
                pckts(state)
            elif command == 'display':
                display(state)
            elif command == 'disable' and len(cmd) == 2:
                disable()
            elif command == 'crash':
                crash(state)
                state['stop'].set()
                break
            elif command == 'exit':
                print("Exiting program...")
                state['stop'].set()
                break
            else:
                print("Invalid command. Please try again.")
                print("Type 'help' for a list of available commands.")
        except Exception as e:
            print(f"Error processing command: {e}")

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
    servers, l = read_top(args.topology)
    st = state(servers, l, args.interval)

    try:
        cmnds(st)
    finally:
        st['stop'].set()
        st['sock'].close()
        print("Server stopped.")

if __name__ == "__main__":
    main()


