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

    first_server_id = None
    
    # assign server dictionary
    for i in range(2, 2 + num_servers):
        line = data[i].split()
        srv_id = int(line[0])
        ip = line[1]
        port = int(line[2])

        if first_server_id is None:
            first_server_id = srv_id
        
        servers.update({srv_id:(ip,port)})
        
    # assign remaining lines to rc
    for j in range(2 + num_servers, 2 + num_servers + num_neighbors):
        line = data[j].split()
        rc.append(line)
        
    return servers, rc, first_server_id
'''

    Command: def state(): 
        Sets up information for the distance vector server. Depends on servers, rc and interval
        in order to create the socket, neighbors, routing table and state data

'''
def state(servers, rc, interval, first_server_id):
    # user server ID 
    user = first_server_id
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
    base_cost = dict(neighbors)
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
            rt[srv_id] = (-1, INF)
    # UDP socket for sending/receiving
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((my_ip, my_port))
    sock.settimeout(1.0)
    # track when neighbor heard from last
    last = {n: 0.0 for n in neighbors}
    # state dictionary
    state = {
        'servers' : servers,
        'neighbors' : neighbors,
        'base_cost' : base_cost,
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

def handle_link_update(state, link_info):
    server1 = int(link_info['server1'])
    server2 = int(link_info['server2'])
    cost = int(link_info['cost'])
    with state['lock']:
        if state['user'] == server1 and server2 in state['neighbors']:
            # This means the user is server1 and server2 is a neighbor, so we update the cost
            state['neighbors'][server2] = cost
            state['base_cost'][server2] = cost
            state['rt'][server2] = (server2, cost)
        elif state['user'] == server2 and server1 in state['neighbors']:
            # This means the user is server2 and server1 is a neighbor, so we update the cost
            state['neighbors'][server1] = cost
            state['base_cost'][server1] = cost
            state['rt'][server1] = (server1, cost)

def update_neighbor_status(state, from_server):
    with state['lock']:
        state['pkts'] += 1
        if from_server in state['neighbors']:
            # update last heard time
            state['last'][from_server] = time.time()
            
            # if neighbor was marked as INF, reset to base cost
            if state['neighbors'][from_server] >= INF:
                base = state['base_cost'].get(from_server, INF)
                state['neighbors'][from_server] = base
                state['rt'][from_server] = (from_server, base)

'''

    Command: def rx():
        Receive incoming UDP packets.

'''
def rx(state):
    while not state['stop'].is_set():
        try:
            # wait for incoming data
            data, addr = state['sock'].recvfrom(1024)
            # decode and parse the packet
            packet = json.loads(data.decode('utf-8'))

            # identify which server sent the packet + info about neighbors
            from_server = int(packet['user'])
            
            neighbor_vector = packet['rt']

            if packet.get('reason') == 'step':
                print(f"RECEIVED MESSAGE FROM SERVER {addr}")

            if 'link_update' in packet:
                handle_link_update(state, packet['link_update'])

            # update the 'last' heard time from sender
            update_neighbor_status(state, from_server)

            # call bell_ford() to apply distance vector updates
            bell_ford(state, from_server, neighbor_vector)
        except socket.timeout:
            continue
        except json.JSONDecodeError:
            continue 
        except OSError as e:
            if e.winerror != 10054:  # Ignore "Connection reset by peer" error
                print(f"Socket error: {e}")
        except Exception as e:
            if not state['stop'].is_set():
                print(f"Error receiving packet: {e}")

'''

    Command: def tx():
        Handles periodic updates and neighbor checks

'''
def tx(state):
    # continuously listen for incoming packets
    while not state['stop'].is_set():
        # Check for dead neighbors
        dead_neigh(state)
        # wait for incoming data
        snd_update(state)
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
        _, c2s = state['rt'].get(snd, (-1, INF))

        # check  destination (sender) knows
        for dstr, sndc in snd_rt.items():
            # convert json to int
            d = int(dstr)
            sndc = int(sndc)

            # compute cost via sender
            if c2s == INF or sndc == INF:
                new = INF
            else:
                new = c2s + sndc

            # current -> table
            _, curr = state['rt'].get(d, (-1, INF))

            # update if new path is cheaper
            if new < curr:
                state['rt'][d] = (snd, new)
            
            # if sender's cost to destination is INF, mark as unreachable
            if _ == snd and new != curr:
                state['rt'][d] = (snd, new)
                continue


'''

    Command: def data_pckt():
        Builds the routing update packet

'''
def data_pckt(state, reason=None, link_update=None):
    with state['lock']:
        rt_cost = {server_id: cost for server_id, (hop, cost) in state['rt'].items()}
    packet = {
        'user' : state['user'],
        'my_ip' : state['my_ip'],
        'my_port' : state['my_port'],
        'rt' : rt_cost
    }
    # add reason for udpate if provided
    if reason is not None:
        packet['reason'] = reason

    # add link update packet if provided
    if link_update is not None:
        server1, server2, cost = link_update
        packet['link_update'] = {
            'server1': server1,
            'server2': server2,
            'cost': cost
        }
    return json.dumps(packet).encode('utf-8')

'''

    Command: def snd_update():
        Sends routing updates to all neighbors, uses data_pckt to build packet and send it 
        through UDP socket.

'''
def snd_update(state, reason=None, link_update=None):
    # build packet
    pckt = data_pckt(state, reason=reason, link_update=link_update)

    with state['lock']:
    # go through each neighbor and send the packet
        targets = [(n_id, state['servers'][n_id]) for n_id in state['neighbors'] if n_id in state['servers']]
        for n_id, (ip, port) in targets:
            try:
                state['sock'].sendto(pckt,(ip, port))
            # ignore send error (stops program from crashing)
            except Exception:
                pass

# helper function to invalidate routes through any neighbors
def invalidate_routes(state, neighbor_id):
    for dest_id in list(state['rt'].keys()):
        hop, _ = state['rt'][dest_id]
        if hop == neighbor_id:
            state['rt'][dest_id] = (-1, INF)

'''

    Command: def dead_neigh():
        Detects and handles dead neighbors

'''
def dead_neigh(state):
    # get current time
    now = time.time()
    # calculate max interval for inactivity
    max_interval = state['interval'] * 3

    with state['lock']:
        # loop through neighbors and check last heard time
        for neighbor_id in list(state['neighbors'].keys()):
            # check last heard time for neighbor
            last_time = state['last'].get(neighbor_id, 0)
            # if last heard time is within max interval, continue
            if now - last_time <= max_interval:
                continue
            # if neighbor is already marked as INF, skip
            if state['neighbors'][neighbor_id] >= INF:
                continue

            state['neighbors'][neighbor_id] = INF
            state['rt'][neighbor_id] = (neighbor_id, INF)
            invalidate_routes(state, neighbor_id)
                
'''

    Command: def update():
        Changes the cost of a link between two servers

    To Do:
        - take two server IDs and a new cost from user
        - update the cost in neighbors & routing table
        - print 

'''
def update(state, server1, server2, cost):
    server1, server2 = int(server1), int(server2)
    if isinstance(cost, str) and cost.lower() == 'inf':
        cost = INF
    else:
        cost = int(cost)

    if state['user'] == server1:
        neighbor = server2
    elif state['user'] == server2:
        neighbor = server1
    else:
        print("Error: One of the servers must be the user server.")
        return
    with state['lock']:
        # update neighbor cost
        state['neighbors'][neighbor] = cost
        state['base_cost'][neighbor] = cost
        # update routing table for neighbor
        state['rt'][neighbor] = (neighbor, cost)
    print("UPDATE SUCCESS")
    snd_update(state, reason='update', link_update=(server1, server2, cost))

'''

Command: def step():
    manually triggers an update message

'''
def step(state):
    print('Sending routing update.')
    snd_update(state, reason='step')

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
        Displays the current routing table - prints each destination, current path cost and next hop.

'''
def display(state):
    # routing table not modified while print ('lock')
    with state['lock']:
        print("dest     |     cost     |     next hop")
        
        # go through each destination
        for dest in sorted(state['rt'].keys()):
            hop, cost = state['rt'][dest]
            # format for cost (unreachable -> INF)
            if cost >= INF:
                c = "INF"
            # int to string
            else:
                c = str(cost)
            # format for hop (unreachable -> blank)
            if hop == -1 or cost >= INF:
                h = ''
            # int to string
            else:
                h = str(hop)
            
            print(f"{dest:<9}|{c:^14}|{h:^14}")

'''

    Command: def disable():
        Disables a link to a neighbor

    To Do:
        - take a neighbor ID as input
        - set that neigbors cost to INF in table
        - update routing table (disconnection)
        - print

'''
# helper function to recalculate routes after disabling a neighbor
def recalculate_routes(state):
    for server_id in state['servers']:
        if server_id == state['user']:
            state['rt'][server_id] = (server_id, 0)
        elif server_id in state['neighbors']:
            cost = state['neighbors'][server_id]
            if cost >= INF:
                state['rt'][server_id] = (-1, INF)
            else:
                state['rt'][server_id] = (server_id, cost)
        else:
            state['rt'][server_id] = (-1, INF)

def disable(state, server_id):
    server_id = int(server_id)

    with state['lock']:
        if server_id not in state['neighbors']:
            print(f"Error: Server {server_id} is not a neighbor.")
            return
        
        #set neighbor cost to INF
        state['neighbors'][server_id] = INF
        state['base_cost'][server_id] = INF

        recalculate_routes(state)

        # update routing table for all destinations that use this neighbor as hop
        for dest_id in list(state['rt'].keys()):
            hop, cost = state['rt'][dest_id]
            if hop == server_id:
                state['rt'][dest_id] = (-1, INF)
    print(f"SUCCESS: Link to neighbor {server_id} disabled.")
    # send update to neighbors about the link cost change
    snd_update(state, reason='update', link_update=(state['user'], server_id, INF))
    time.sleep(0.2)  # Give time for the update to propagate
    # send another update to ensure all neighbors are aware of the change
    snd_update(state, reason='step')

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
                update(state, cmd[1], cmd[2], cmd[3])
            elif command == 'step':
                step(state)
            elif command == 'pckts':
                pckts(state)
            elif command == 'display':
                display(state)
            elif command == 'disable' and len(cmd) == 2:
                disable(state, cmd[1])
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
        except KeyboardInterrupt:
            print("\nExiting program...")
            state['stop'].set()
            break
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
    servers, l, first_server_id = read_top(args.topology)
    st = state(servers, l, args.interval, first_server_id)

    rcv_thread = threading.Thread(target=rx, args=(st,), daemon=True)
    rcv_thread.start()

    tsm_thread = threading.Thread(target=tx, args=(st,), daemon=True)
    tsm_thread.start()

    time.sleep(1)  # Give threads time to start

    try:
        cmnds(st)
    finally:
        st['stop'].set()

        rcv_thread.join(timeout=1.0)
        tsm_thread.join(timeout=1.0)

        st['sock'].close()
        print("Server stopped.")

if __name__ == "__main__":
    main()


