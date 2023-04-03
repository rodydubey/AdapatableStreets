import argparse
import torch
import time
import os
import numpy as np
from gym.spaces import Box, Discrete
from pathlib import Path
from torch.autograd import Variable
# from tensorboardX import SummaryWriter

from utils.buffer import ReplayBuffer
from algorithms.maddpg import MADDPG

import numpy as np
import sys
sys.path.append('C:/D/SUMO/MARL/multiagentRL/')
from gym_sumo.envs import SUMOEnv
from matplotlib import pyplot as plt
import warnings
warnings.filterwarnings('ignore')
import wandb
from argparse import ArgumentParser
from utils.env_wrappers import SubprocVecEnv, DummyVecEnv
import time
import os
from tqdm import tqdm
import csv
from gym_sumo.envs.utils import generateFlowFiles
from gym_sumo.envs.utils import plot_scores
from gym_sumo.envs.utils import print_status

display = 'DISPLAY' in os.environ
use_gui = True
mode = 'gui' if (use_gui and display) else 'none'

USE_CUDA = False  # torch.cuda.is_available()

# mode = 'gui'

generateFlowFiles("Test 0")
def make_parallel_env(env_id, n_rollout_threads, seed, discrete_action):
    def get_env_fn(rank):
        def init_env():
            env = SUMOEnv(mode=mode)
            env.seed(seed + rank * 1000)
            np.random.seed(seed + rank * 1000)
            return env
        return init_env
    if n_rollout_threads == 1:
        return DummyVecEnv([get_env_fn(0)])
    else:
        return SubprocVecEnv([get_env_fn(i) for i in range(n_rollout_threads)])
    
def run(config):
    model_dir = Path('./models') / config.env_id / config.model_name
    curr_run = config.run_id + config.model_id
    run_dir = model_dir / curr_run
    log_dir = run_dir / 'logs'

    torch.manual_seed(config.seed)
    np.random.seed(config.seed)
    if not USE_CUDA:
        torch.set_num_threads(config.n_training_threads)

    env = make_parallel_env(config.env_id, config.n_rollout_threads, config.seed,
                            config.discrete_action)
    print(env.action_space)
    print(env.observation_space)
    env.setInitialParameters(True)

    maddpg = MADDPG.init_from_save(run_dir)
    t = 0
    scores = []    
    smoothed_total_reward = 0
    pid = os.getpid()
    testResultFilePath = f"results/static_test_surge_{config.run_id}.csv"  
    with open(testResultFilePath, 'w', newline='') as file:
        writer = csv.writer(file)
        # writer.writerow(['Car_Flow_Rate','Bike_Flow_Rate','Ped_Flow_Rate','Car_Lane_Width','Bike_Lane_Width','Ped_Lane_Width','Co_Sharing', \
        #         'Total_occupancy_car_Lane','Total_occupancy_bike_Lane','Total_occupancy_ped_Lane','total_density_bike_lane','total_density_ped_lane','total_density_car_lane','RewardAgent_0', 'RewardAgent_1','RewardAgent_2','LevelOfService'])

        writer.writerow(['avg_waiting_time_car','avg_waiting_time_bike','avg_waiting_time_ped','avg_queue_length_car','avg_queue_length_bike','avg_queue_length_ped','los',"Reward_Agent_2","cosharing",'timeslot'])

        for ep_i in tqdm(range(0, config.n_episodes, config.n_rollout_threads)):
            total_reward = 0
            print("Episodes %i-%i of %i" % (ep_i + 1,
                                            ep_i + 1 + config.n_rollout_threads,
                                            config.n_episodes))
            obs = env.reset(mode)
            step = 0
            # obs.shape = (n_rollout_threads, nagent)(nobs), nobs differs per agent so not tensor
            maddpg.prep_rollouts(device='cpu')

            # explr_pct_remaining = max(0, config.n_exploration_eps - ep_i) / config.n_exploration_eps
            # maddpg.scale_noise(config.final_noise_scale + (config.init_noise_scale - config.final_noise_scale) * explr_pct_remaining)
            # maddpg.reset_noise()
        
            for et_i in range(config.episode_length):
                step += 1
               
                torch_obs = [Variable(torch.Tensor(np.vstack(obs[:, i])),
                                    requires_grad=False)
                            for i in range(maddpg.nagents)]
                # get actions as torch Variables
                torch_agent_actions = maddpg.step(torch_obs, explore=True)
                # convert actions to numpy arrays
                agent_actions = [ac.data.numpy() for ac in torch_agent_actions]
                # rearrange actions to be per environment
                actions = [[ac[i] for ac in agent_actions] for i in range(config.n_rollout_threads)]
                next_obs, rewards, dones, infos = env.step(actions)
                obs = next_obs
                t += config.n_rollout_threads
                total_reward += rewards[0]
                # carFlowRate,bikeFlowRate,pedFlowRate,carLaneWidth,bikeLaneWidth,pedlLaneWidth,cosharing,total_mean_speed_car,total_mean_speed_bike,total_mean_speed_ped,total_waiting_car_count,total_waiting_bike_count, total_waiting_ped_count,total_unique_car_count,total_unique_bike_count,total_unique_ped_count, \
                #     car_occupancy,bike_occupancy,ped_occupancy,collision_count_bike,collision_count_ped,total_density_bike_lane,total_density_ped_lane, total_density_car_lane,Hinderance_bb,Hinderance_bp,Hinderance_pp,levelOfService = env.testAnalysisStats()
            
            
                # rewardAgent_0, rewardAgent_1,rewardAgent_2 = env.rewardAnalysisStats()

                avg_waiting_time_car,avg_waiting_time_bike,avg_waiting_time_ped,avg_queue_length_car,avg_queue_length_bike,avg_queue_length_ped,los,reward_agent_2,cosharing = env.getTestStats()

                # rewardAgent_2 = 0
                writer.writerow([avg_waiting_time_car,avg_waiting_time_bike,avg_waiting_time_ped,avg_queue_length_car,avg_queue_length_bike,avg_queue_length_ped,los,reward_agent_2,cosharing,ep_i])

            total_reward /= step
            # show reward
            smoothed_total_reward = smoothed_total_reward * 0.9 + total_reward * 0.1
            scores.append(smoothed_total_reward)
        
        env.close()
      
    plt.plot(scores)
    plt.xlabel('episodes')
    plt.ylabel('ave rewards')
    plt.savefig('avgScore.jpg')
    plt.show()
        # logger.export_scalars_to_json(str(log_dir / 'summary.json'))
        # logger.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--env_id", default="simple", type=str)
    parser.add_argument("--run_id", default="run74", type=str) # run47 is performing the best on training data
    parser.add_argument("--model_id", default="/model.pt", type=str)
    parser.add_argument("--model_name", default="simple_model", type=str)
    parser.add_argument("--seed",
                        default=1, type=int,
                        help="Random seed")
    parser.add_argument("--n_rollout_threads", default=1, type=int)
    parser.add_argument("--n_training_threads", default=6, type=int)
    parser.add_argument("--buffer_length", default=int(1e6), type=int)
    parser.add_argument("--n_episodes", default=48, type=int)
    parser.add_argument("--episode_length", default=6, type=int)
    parser.add_argument("--steps_per_update", default=10, type=int)
    parser.add_argument("--batch_size",
                        default=1024, type=int,
                        help="Batch size for model training")
    parser.add_argument("--n_exploration_eps", default=25000, type=int)
    parser.add_argument("--init_noise_scale", default=0.3, type=float)
    parser.add_argument("--final_noise_scale", default=0.0, type=float)
    parser.add_argument("--save_interval", default=30, type=int)
    parser.add_argument("--hidden_dim", default=64, type=int)
    parser.add_argument("--lr", default=0.01, type=float)
    parser.add_argument("--tau", default=0.01, type=float)
    parser.add_argument("--agent_alg",
                        default="MADDPG", type=str,
                        choices=['MADDPG', 'DDPG'])
    parser.add_argument("--adversary_alg",
                        default="MADDPG", type=str,
                        choices=['MADDPG', 'DDPG'])
    parser.add_argument("--discrete_action",
                        action='store_true')

    config = parser.parse_args()

    run(config)
