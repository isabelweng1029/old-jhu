# Daniel Deutsch
# Dan Crankshaw
# Ryan 'the Beast' Cotterell
#    "Two T's, two E's, two L's" - the family motto

import sys;

# This will figure out the dimensions of the grid
def get_dimensions_and_landmarks(network_lines):
    
    row = -1;
    col = -1;
    landmarks = -1;
        
    for line in network_lines:
        if line.startswith("PositionRow_"):
            line_split = line.split(",");
            row = line_split[-1].rstrip("\n");
            break;
    
    for line in network_lines:
        if line.startswith("PositionCol_"):
            line_split = line.split(",");
            col = line_split[-1].rstrip("\n");
            break;
        
    for line in network_lines:
        if line.startswith("ObserveLandmark"):
            observation,_,_ = line.split(" ")[0].split("_");
            landmarks = max(landmarks, observation[-1]);
   
    return int(row), int(col), int(landmarks);
            

# will read in the PositionRow_t+1 | PositionRow_t, Action and
# PositionCol_t+1 | PositionCol_t, Action conditional probability tables.
def read_position_cpt(training_lines):
    
    # initialize the CPT
    row_cpt = {};
    col_cpt = {};
    actions = ["MoveNorth", "MoveEast", "MoveSouth", "MoveWest"];
    
    for action in actions:
        row_cpt["PositionRow_t+1=i|PositionRow_t=i-1,Action_t=" + action] = 1;
        row_cpt["PositionRow_t+1=i|PositionRow_t=i+1,Action_t=" + action] = 1;
        row_cpt["PositionRow_t+1=i|PositionRow_t=i,Action_t=" + action] = 1;
        col_cpt["PositionCol_t+1=j|PositionCol_t=j-1,Action_t=" + action] = 1;
        col_cpt["PositionCol_t+1=j|PositionCol_t=j+1,Action_t=" + action] = 1;
        col_cpt["PositionCol_t+1=j|PositionCol_t=j,Action_t=" + action] = 1;
        
    # indicate we're starting a new trajectory
    trajectory = -1;
    previousRow = -1;
    previousCol = -1;
    previousAction = "";
    
    # need to keep track of how many times each move happens
    moveCounters = {"MoveNorth" : 0, "MoveEast" : 0, "MoveSouth" : 0, "MoveWest" : 0};
    
    for line in training_lines:
        
        line_split = line.split(" ");

        # we're starting a new trajectory
        if line_split[0] != trajectory:
            trajectory = line_split[0];
            _,previousRow = line_split[2].rstrip("\n").split("=");
            _,previousCol = line_split[3].rstrip("\n").split("=");
            _,previousAction = line_split[4].rstrip("\n").split("=");
            continue;
              
        # get the current position and action
        _,row = line_split[2].rstrip("\n").split("=");
        _,col = line_split[3].rstrip("\n").split("=");
        _,action = line_split[4].rstrip("\n").split("=");
        
        # figure out the row change
        positionChange = "";
        if (row == previousRow):
            positionChange = "i";
        elif (int(row) + 1 == int(previousRow)):
            positionChange = "i+1";
        else:
            positionChange = "i-1";
        
        # update the row_cpt
        expression = "PositionRow_t+1=i|PositionRow_t=" + positionChange + ",Action_t=" + previousAction;        
        row_cpt[expression] = row_cpt[expression] + 1;

        # figure out the column change
        if (col == previousCol):
            positionChange = "j";
        elif (int(col) + 1 == int(previousCol)):
            positionChange = "j+1";
        else:
            positionChange = "j-1";

        # update the col_cpt
        expression = "PositionCol_t+1=j|PositionCol_t=" + positionChange + ",Action_t=" + previousAction;
        col_cpt[expression] = col_cpt[expression] + 1;
        
        # update move counter since we used that action
        moveCounters[previousAction] = moveCounters[previousAction] + 1;
        
        # update the previous values
        previousRow = row;
        previousCol = col;
        previousAction = action;
    
    # need to now make them probabilities
    # normalize by the number of times we saw that action + 3 for Laplacian smoothing
    for action in actions:
        row_cpt["PositionRow_t+1=i|PositionRow_t=i-1,Action_t=" + action] = float(row_cpt["PositionRow_t+1=i|PositionRow_t=i-1,Action_t=" + action] / float(3 + moveCounters[action]));
        row_cpt["PositionRow_t+1=i|PositionRow_t=i+1,Action_t=" + action] = float(row_cpt["PositionRow_t+1=i|PositionRow_t=i+1,Action_t=" + action] / float(3 + moveCounters[action]));
        row_cpt["PositionRow_t+1=i|PositionRow_t=i,Action_t=" + action] = float(row_cpt["PositionRow_t+1=i|PositionRow_t=i,Action_t=" + action] / float(3 + moveCounters[action]));
        col_cpt["PositionCol_t+1=j|PositionCol_t=j-1,Action_t=" + action] = float(col_cpt["PositionCol_t+1=j|PositionCol_t=j-1,Action_t=" + action] / float(3 + moveCounters[action]));
        col_cpt["PositionCol_t+1=j|PositionCol_t=j+1,Action_t=" + action] = float(col_cpt["PositionCol_t+1=j|PositionCol_t=j+1,Action_t=" + action] / float(3 + moveCounters[action]));
        col_cpt["PositionCol_t+1=j|PositionCol_t=j,Action_t=" + action] = float(col_cpt["PositionCol_t+1=j|PositionCol_t=j,Action_t=" + action] / float(3 + moveCounters[action]));
    
    return row_cpt, col_cpt;
        
# This will compute the CPTs for Observation_?_T | PositionRow_t, PositionCol_t
def read_observation_cpt(training_lines, rows, columns, numLandmarks):

    # initialize the CPTs
    wall_cpt = {};
    land_cpt = {};
    position_counter = {};
    
    directions = ["N", "E", "S", "W"];
    
    for direction in directions:
        for row in range(1, rows + 1):
            for col in range(1, columns + 1):
                position_counter[str(row) + "," + str(col)] = 0;
                
                wall_cpt["ObserveWall_" + direction + "_t|PositionRow_t=" + str(row) + ",PositionCol_t=" + str(col)] = 1;
                
                for land in range(1, numLandmarks + 1):
                    land_cpt["ObserveLandmark" + str(land) + "_" + direction + "_t|PositionRow_t=" + str(row) + ",PositionCol_t=" + str(col)] = 1;
        
    for line in training_lines:
        line_split = line.split(" ");
        _,row = line_split[2].rstrip("\n").split("=");
        _,col = line_split[3].rstrip("\n").split("=");
        position_counter[row + "," + col] = position_counter[row + "," + col] + 1;
        
        # there could be many observations at one point
        for i in range(5, len(line_split)):
                
            # breaks up the line "ObserveLandmark2_N_0=True"
            observation,direction,_ = line_split[i].split("=")[0].split("_");
            
            if observation.startswith("ObserveWall"):
                expression = "ObserveWall_" + direction + "_t|PositionRow_t=" + row + ",PositionCol_t=" + col;
                wall_cpt[expression] = wall_cpt[expression] + 1;
            else:
                expression = observation + "_" + direction + "_t|PositionRow_t=" + row + ",PositionCol_t=" + col;
                land_cpt[expression] = land_cpt[expression] + 1;
                
    
    # need to make them into probabilities
    for row in range(1, rows + 1):
        for col in range(1, columns + 1):
            for direction in directions:
                
                wall_cpt["ObserveWall_" + direction + "_t|PositionRow_t=" + str(row) + ",PositionCol_t=" + str(col)] = float(wall_cpt["ObserveWall_" + direction + "_t|PositionRow_t=" + str(row) + ",PositionCol_t=" + str(col)]) / float(2 + position_counter[str(row) + "," + str(col)]);
                
                for land in range(1, numLandmarks + 1):
                    land_cpt["ObserveLandmark" + str(land) + "_" + direction + "_t|PositionRow_t=" + str(row) + ",PositionCol_t=" + str(col)] = float(land_cpt["ObserveLandmark" + str(land) + "_" + direction + "_t|PositionRow_t=" + str(row) + ",PositionCol_t=" + str(col)]) / (float(2 + position_counter[str(row) + "," + str(col)]));
    
    print position_counter["1,1"];
    
    return wall_cpt, land_cpt;
    
def main():
    
    # check for command line args
    if (len(sys.argv) != 4):
        print "Please provide the network, training, and cpd-output files";
        exit();

    # read the network file
    network_lines = open(sys.argv[1]).readlines();
    num_variables = int(network_lines[0].rstrip("\n"));
    
    # get the dimensions of the grid
    rows,columns,landmarks = get_dimensions_and_landmarks(network_lines);
    
    # read in the possible values for each variable
    possible_values = {};
    for i in range(1, num_variables + 1):
        
        # break up the variable and the values
        line = network_lines[i].rstrip("\n");
        variable,values = line.split(" ");
        values = values.split(",");
    
        # place the values in the hashmap
        possible_values[variable] = values;
        
    # open the training data
    training_lines = open(sys.argv[2]).readlines();

    positionRow_cpt, positionCol_cpt = read_position_cpt(training_lines);

    wall_cpt, land_cpt = read_observation_cpt(training_lines, rows, columns, landmarks);

#    print positionRowCPT;
#    print positionColCPT;
#    print wall_cpt;
#    print land_cpt;

    print positionRow_cpt["PositionRow_t+1=i|PositionRow_t=i-1,Action_t=MoveNorth"];
    print positionRow_cpt["PositionRow_t+1=i|PositionRow_t=i,Action_t=MoveNorth"];
    print positionRow_cpt["PositionRow_t+1=i|PositionRow_t=i+1,Action_t=MoveNorth"];

    print wall_cpt["ObserveWall_N_t|PositionRow_t=1,PositionCol_t=1"];
    
    
    
    
    

if __name__ == "__main__":
    main();
    
    
    
    
    
    
    