#!/usr/bin/python
# -*- coding:utf-8 -*-

import argparse
import os
from datetime import datetime
from utils.logger import setlogger
import logging
from utils.train_utils_leak import train_utils

import torch
import warnings
print(torch.__version__)
warnings.filterwarnings('ignore')
import matplotlib.pyplot as plt


import sys
sys.setrecursionlimit(100000)


args = None

def parse_args():
    parser = argparse.ArgumentParser(description='Train')

    # model and data parameters
    parser.add_argument('--model_name', type=str, default='LORA_Net_12345', help='the name of the model')
    parser.add_argument('--data_name', type=str, default='leak_signals', help='the name of the data')
    # parser.add_argument('--data_name', type=str, default='JNU', help='the name of the data')
    parser.add_argument('--data_dir', type=str, default=r'E:\projects\UDTL-LoRA\data\leak_signals', help='the directory of the data')
    # parser.add_argument('--data_dir', type=str, default=r'/home/t/projects/UDTL_master/data/JNU', help='the directory of the data')
    parser.add_argument('--transfer_task', type=list, default=[[0], [1], [2], [3]], help='transfer learning tasks')
    parser.add_argument('--task', type=str, default='0-123', help='transfer learning tasks')
    parser.add_argument('--num_layers', type=str, default='2', help='num_layers in model')
    parser.add_argument('--note', type=str, default='no.1,3,5    数据增强改动 原始:(-100,400),(0.5,1.5)     [1,1,1,1] bs=128,2 ')
    parser.add_argument('--normlizetype', type=str, default='mean-std', help='nomalization type')
    parser.add_argument('--set_input', type=str, default='T F', help='nomalization type')
    parser.add_argument('--eval_test_all', type=bool, default=False, help='')

    # adabn parameters
    parser.add_argument('--adabn', type=bool, default=False, help='whether using adabn')
    parser.add_argument('--eval_all', type=bool, default=True, help='whether using all samples to update the results')
    parser.add_argument('--adabn_epochs', type=int, default=3, help='the number of training process')


    # training parameters
    parser.add_argument('--cuda_device', type=str, default='0', help='assign device')
    parser.add_argument('--checkpoint_dir', type=str, default='.\checkpoint_adabn', help='the directory to save the model')
    parser.add_argument("--pretrained", type=bool, default=False, help='whether to load the pretrained model')
    parser.add_argument('--batch_size', type=int, default=32, help='batchsize of the training process')
    parser.add_argument('--num_workers', type=int, default=0, help='the number of training process')

   # fine paramenters
    parser.add_argument('--source_num_classes', type=int, default=12, help='源域泄露孔径位置类别')
    parser.add_argument('--target_num_classes', type=int, default=12, help='目标域泄露孔径位置数目')
    parser.add_argument('--target_label', type=str, default=['2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13' ] ,help='')
    parser.add_argument('--target_classes', type=str, default=[[2], [3], [4], [5], [6], [7], [8], [9], [10], [11], [12], [13] ], help='')

    parser.add_argument('--Fine', type=bool, default=False, help='是否进行Fine')
    parser.add_argument('--Fine_1', type=bool, default=True, help='是否进行微调训练')  

    parser.add_argument('--model_Fine_name', type=str, default='LORA_Net_12345', help='加载微调模型')

    parser.add_argument('--Fine_number', type=int, default=1, help='use one-shot、three-shot、five-shot、ten-shot for every classes in taget domain')


    
    #parser.add_argument('--model_Fine', type=str, default=r'E:\projects\UDTL-LoRA\checkpoint_adabn\1120-200710_LORA_Net_12345_F0-123-[1]\fine_tuned_2_0.9950980392156865_1.pth' , help='')
   
    # parser.add_argument('--param_zero', type=bool, default=False , help='参数清零')

    # parser.add_argument('--Fine_epoch', type=int, default='50' , help='')
    # parser.add_argument('--Fine_lr', type=float, default='0.01' , help='')



    # parser.add_argument('--Fine_classes', type=bool, default=True, help='是否微调类别数')
    # parser.add_argument('--Fine_num_classes', type=int, default=6, help='微调任务中泄露孔径类别数')


    # optimization information
    parser.add_argument('--opt', type=str, choices=['sgd', 'adam'], default='adam', help='the optimizer')
    parser.add_argument('--lr', type=float, default=1e-3, help='the initial learning rate')
    parser.add_argument('--momentum', type=float, default=0.9, help='the momentum for sgd')
    parser.add_argument('--weight-decay', type=float, default=1e-5, help='the weight decay')
    parser.add_argument('--lr_scheduler', type=str, choices=['step', 'exp', 'stepLR', 'fix'], default='step', help='the learning rate schedule')
    parser.add_argument('--gamma', type=float, default=0.66, help='learning rate scheduler parameter for step and exp')
    parser.add_argument('--steps', type=str, default='100, 150', help='the learning rate decay for step and stepLR')


    # save, load and display information
    parser.add_argument('--max_epoch', type=int, default=200, help='max number of epoch')
    parser.add_argument('--print_step', type=int, default=600, help='the interval of log training information')

    args = parser.parse_args()
    return args

if __name__ == '__main__':

    print("1"==1)

    args = parse_args()
    os.environ['CUDA_VISIBLE_DEVICES'] = args.cuda_device.strip()
    # Prepare the saving path for the model
    sub_dir = datetime.strftime(datetime.now(), '%m%d-%H%M%S') + '_' + args.model_name + '_' + args.task
    save_dir = os.path.join(args.checkpoint_dir, sub_dir)
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    # set the logger
    setlogger(os.path.join(save_dir, 'train.log'))

    # save the args
    for k, v in args.__dict__.items():
        logging.info("{}: {}".format(k, v))
    
    

    trainer = train_utils(args, save_dir)
    trainer.setup()
    trainer.train()


    if args.Fine == False:
        # 创建图表
        fig, axs = plt.subplots(3, 2, figsize=(15, 15))
        #fig, axs = plt.subplots(3, 2, figsize=(15, 15))

        # 绘制损失值曲线
        plt.plot(trainer.train_dict['source_train-Loss'], label='Loss')
        plt.plot(trainer.train_dict['source_val-Loss'], label='Loss')
        plt.plot(trainer.train_dict['target_val-Loss'], label='Loss')

        # 绘制准确率（定位）曲线
        plt.plot(trainer.train_dict['source_train-Acc_pos'], label='Accuracy (Position)')
        plt.plot(trainer.train_dict['source_val-Acc_pos'], label='Accuracy (Position)')
        plt.plot(trainer.train_dict['target_val-Acc_pos'], label='Accuracy (Position)')

        

        # # 添加图例
        # plt.legend()
        # # 添加标题和轴标签
        # plt.title('Training Metrics')
        # plt.xlabel('Epoch')
        # plt.ylabel('Value')
        fig, axs = plt.subplots(3, 2, figsize=(15, 15))
        # 定义子图标题
        titles = ['Loss', 'Accuracy (Positive)']
        # 定义数据集名称
        datasets = ['source_train', 'source_val', 'target_val']
        # 定义数据集键
        keys = ['Loss', 'Acc_pos']
        # 绘制6个图
        for i, dataset in enumerate(datasets):
            for j, key in enumerate(keys):
                ax = axs[i, j]
                data = trainer.train_dict[f'{dataset}-{key}']
                ax.plot(data)
                ax.set_title(f'{dataset} - {titles[j]}')
                ax.set_xlabel('Epoch')
                ax.set_ylabel('Value')
        # 调整子图之间的间距    
        plt.tight_layout()
        plt.savefig(os.path.join(save_dir, 'result.jpg'), bbox_inches='tight')
    # # # 显示图形
    # plt.show()
    
    
    # 创建图表
    # fig, axs = plt.subplots(figsize=(15, 15))
    # #fig, axs = plt.subplots(3, 2, figsize=(15, 15))
    # # 绘制曲线
    # x_values = [1, 3, 5, 10]
    # plt.plot(x_values, trainer.Fine_dict['Fine_Acc'])
    # # # 添加图例
    # ax.legend()
    # # # 添加标题和轴标签
    # # ax.title('Fine Results')
    # ax.set_xlabel('Fine number')
    # ax.set_ylabel('Fine Acc')
    # # 设置横轴刻度
    # ax.set_xticks(x_values)

    # plt.savefig(os.path.join(save_dir, 'Fine_result.jpg'), bbox_inches='tight')
    


    # plt.savefig(os.path.join(save_dir, 'result.jpg'), bbox_inches='tight')

    # plt.savefig(f'./log/{log_time_str}/loss_accuracy.jpg', bbox_inches='tight')

   



