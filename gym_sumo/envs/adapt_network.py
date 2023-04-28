# adaptNetwork.py

import xml.etree.ElementTree as ET
from sumolib import checkBinary
import sys
import numpy as np
import subprocess

from_tos = {'E0': 'E2',
            '-E1': 'E3',
            '-E2': '-E0',
            '-E3': 'E1'}

baselineCarLaneWidth = 9.6
baselinebicycleLaneWidth = 1.5
baselinePedestrianLaneWidth = 1.5
totalEdgeWidth = baselineCarLaneWidth + baselinebicycleLaneWidth + baselinePedestrianLaneWidth
# carLane_width_actions = ['3.2','5.4','6.6','7.8','9.6']
carLane_width_actions = ['3.2','5.6','6.4','7.8','9.6']
bikeLane_width_actions = ['0.1','0.2','0.3','0.4','0.5','0.6','0.7','0.8','0.9']

netconvert = checkBinary("netconvert")
sys.path.append(netconvert)

def clamp(n, minn, maxn):
    return max(min(maxn, n), minn)

#function
def adaptNetwork(env, sumo_edges, base_network,actionDict,modelType,routeFileName,sumoCMD, pid, traci):
    if modelType != 'static':
        # parsing directly.
        tree = ET.parse(base_network)
        root = tree.getroot()
        
        remainderLaneLength = 0
        edge_props = {}

        for (key, edge_id), value in actionDict.items():
            props = edge_props.get(edge_id,{})
            if "agent 0" in key:
                
                if modelType == "heuristic":
                    carLaneWidth = value
                
                else:
                    carLaneWidth = float(carLane_width_actions[value])
                    remainderLaneLength = totalEdgeWidth - carLaneWidth
                props['carLaneWidth'] = carLaneWidth
            elif "agent 1" in key:
                if modelType == "heuristic":
                    bikeLaneWidth = value
                    pedLaneWidth = float(totalEdgeWidth-(carLaneWidth + bikeLaneWidth))
                else:            
                    bikeLaneWidth = float(bikeLane_width_actions[value])*remainderLaneLength
                    pedLaneWidth = float(totalEdgeWidth-(carLaneWidth + bikeLaneWidth))
                props['bikeLaneWidth'] = bikeLaneWidth
                props['pedLaneWidth'] = pedLaneWidth
            elif "agent 2" in key:   
                if value < 1:
                    coShare = 0    
                else:
                    coShare = 1  
                props['coShare'] = coShare
            edge_props[edge_id] = props
            edge_props[from_tos[edge_id]] = props # also set properties of downstream

        for edge_id, props in edge_props.items():
            carLaneWidth = props['carLaneWidth']
            bikeLaneWidth = props['bikeLaneWidth']
            pedLaneWidth = props['pedLaneWidth']
            coShare = props['coShare']
            for lanes in root.iter('lane'):
                if lanes.attrib['id'] == f"{edge_id}_2":
                    lanes.attrib['width'] = repr(carLaneWidth)
                if coShare <= 0.5:            
                    if lanes.attrib['id'] == f"{edge_id}_1":
                        lanes.attrib['width'] = repr(bikeLaneWidth)
                    elif lanes.attrib['id'] == f"{edge_id}_0":
                        lanes.attrib['width'] = repr(pedLaneWidth)
                else:             
                    if lanes.attrib['id'] == f"{edge_id}_0":
                        lanes.attrib['width'] = repr(bikeLaneWidth+pedLaneWidth)
                    elif lanes.attrib['id'] == f"{edge_id}_1":
                        lanes.attrib['width'] = repr(0)
        
        #  write xml 
        modified_netfile = f'environment/intersection2_{pid}.net.xml'
        file_handle = open(modified_netfile,"wb")
        tree.write(file_handle)
        file_handle.close()
        if modified_netfile not in env.generatedFiles:
            env.generatedFiles.append(modified_netfile)
        subprocess.run(f"netconvert -s {modified_netfile} -o {modified_netfile} -W", capture_output=True, shell=True)
    else:
        modified_netfile = base_network
    # call netconvert            
    # netconvert = checkBinary("netconvert")


    # save state
    # traci.simulation.clearPending()
    # traci.simulation.saveState(f'environment/savedstate_{pid}.xml') 
    # load traci simulation   
    # traci.load(['-n', "environment\intersection2.net.xml","--start"])
    currentTime = (env.timeOfHour-1)*6*300 # TODO: fix hardcoded

    # traci.load(sumoCMD + ['-n', 'environment/intersection2.net.xml', '-r', routeFileName, '--additional-files',"environment/intersection2.add.xml"])
    additional_args = ['-n', modified_netfile, '-r', routeFileName]

    # if env._scenario == "Test Single Flow":
    #     additional_args += ['-b', str(currentTime)]
    traci.load(sumoCMD + additional_args)

    # traci.load(['-n', 'environment/intersection2.net.xml', '-r', routeFileName, "--start"]) # should we keep the previous vehic
    # if env._scenario == "Test Single Flow":
    #     traci.simulationStep(currentTime)
    # load last saved state
    # traci.simulation.loadState(f'environment/savedstate_{pid}.xml')

    if modelType != 'static':
        for edge_id, props in edge_props.items():
            carLaneWidth = props['carLaneWidth']
            bikeLaneWidth = props['bikeLaneWidth']
            pedLaneWidth = props['pedLaneWidth']
            coShare = props['coShare']
            #change lane sharing based on agent choice
            if coShare <= 0.5:
                traci.lane.setDisallowed(f'{edge_id}_1', ['all'])
                traci.lane.setAllowed(f'{edge_id}_1', ['bicycle'])
                traci.lane.setDisallowed(f'{edge_id}_0', ['all'])
                traci.lane.setAllowed(f'{edge_id}_0', ['pedestrian'])
            else: 
                traci.lane.setDisallowed(f'{edge_id}_0', ['all'])
                allowed = []
                allowed.append('bicycle')
                allowed.append('pedestrian')        
                traci.lane.setAllowed(f'{edge_id}_0', allowed)
                traci.lane.setDisallowed(f'{edge_id}_1', ["all"])
