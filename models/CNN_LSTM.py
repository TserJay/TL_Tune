
import torch
from torch import nn, optim
import torch.nn.functional as F
from torch.nn import init
import math
from einops import rearrange

# from models.embed import DepthwiseSeparableConv1d, DataEmbedding, MLP

# import summary
# from torchsummary import summary


class MLP(nn.Module):
    """ Very simple multi-layer perceptron (also called FFN)   多层感知器FFN"""

    def __init__(self, input_dim, hidden_dim, output_dim, num_layers):
        super().__init__()
        self.num_layers = num_layers
        h = [hidden_dim] * (num_layers - 1)
        self.layers = nn.ModuleList(nn.Linear(n, k) for n, k in zip([input_dim] + h, h + [output_dim]))

    def forward(self, x):
        for i, layer in enumerate(self.layers):
            x = F.relu(layer(x)) if i < self.num_layers - 1 else layer(x)
        return x


  
    
#全局平均池化+1*1卷积核+ReLu+1*1卷积核+Sigmoid
class SE_Block(nn.Module):
    def __init__(self, inchannel, ratio=16):
        super(SE_Block, self).__init__()
        # 全局平均池化(Fsq操作)
        self.gap = nn.AdaptiveAvgPool1d(1)
        # 两个全连接层(Fex操作)
        self.fc = nn.Sequential(
            nn.Linear(inchannel, inchannel // ratio, bias=False),  # 从 c -> c/r
            nn.ReLU(),
            nn.Linear(inchannel // ratio, inchannel, bias=False),  # 从 c/r -> c
            nn.Sigmoid()
        )
 
    def forward(self, x):
            # 读取批数据图片数量及通道数
            b, c, h = x.size()
            # Fsq操作：经池化后输出b*c的矩阵
            y = self.gap(x).view(b, c)
            # Fex操作：经全连接层输出（b，c，1，1）矩阵
            y = self.fc(y).view(b, c, 1)

            
            # Fscale操作：将得到的权重乘以原来的特征图x
            return x * y.expand_as(x)




class Bottle2neck(nn.Module):
    expansion = 4

    def __init__(self, inplanes, planes, stride=1, downsample=None, baseWidth=26, scale = 4, stype='normal'):
        """ Constructor
        Args:
            inplanes: input channel dimensionality
            planes: output channel dimensionality
            stride: conv stride. Replaces pooling layer.
            downsample: None when stride = 1
            baseWidth: basic width of conv3x3
            scale: number of scale.
            type: 'normal': normal set. 'stage': first block of a new stage.
        """
        super(Bottle2neck, self).__init__()

        width = int(math.floor(planes * (baseWidth/64.0)))
        self.conv1 = nn.Conv1d(inplanes, width*scale, kernel_size=1, bias=False)  
        self.bn1 = nn.BatchNorm1d(width*scale)
        # self.se1 = SE_Block(width*scale)
        
        
        if scale == 1:
          self.nums = 1
        else:
          self.nums = scale -1
        if stype == 'stage':
            self.pool = nn.AvgPool1d(kernel_size=5, stride = stride, padding=2)            
            # self.atten = MixedAttention(width)
            self.se2 = SE_Block(width)
        convs = []
        bns = []
        for i in range(self.nums):
          convs.append(nn.Conv1d(width, width, kernel_size=5, stride = stride, padding=2, bias=False))
          bns.append(nn.BatchNorm1d(width))

        self.convs = nn.ModuleList(convs)
        self.bns = nn.ModuleList(bns)

        self.conv3 = nn.Conv1d(width*scale, planes * self.expansion, kernel_size=1, bias=False)
        self.bn3 = nn.BatchNorm1d(planes * self.expansion)
        # self.se3 = SE_Block(planes * self.expansion)

        self.relu = nn.ReLU(inplace=True)
        self.downsample = downsample
        self.stype = stype
        self.scale = scale
        self.width  = width

    def forward(self, x):
        residual = x

        out = self.conv1(x)
        out = self.bn1(out)
        # out = self.se1(out)  #se模块
     
        out = self.relu(out)

        spx = torch.split(out, self.width, 1)
        for i in range(self.nums):
          if i==0 or self.stype=='stage':
            sp = spx[i]
          else:
            sp = sp + spx[i]
          sp = self.convs[i](sp)
          
          sp = self.relu(self.bns[i](sp))
          if i==0:
            out = sp
          else:
            out = torch.cat((out, sp), 1)
        if self.scale != 1 and self.stype=='normal':
          out = torch.cat((out, spx[self.nums]),1)
        elif self.scale != 1 and self.stype=='stage':
          out = torch.cat((out, self.pool(self.se2(spx[self.nums]))),1)
        #   out = torch.cat((out, self.atten(spx[self.nums])),1)
         

        out = self.conv3(out)
        out = self.bn3(out)
        # out = self.se3(out)

        if self.downsample is not None:
            residual = self.downsample(x)

        out += residual
        out = self.relu(out)

        return out

class Res2Net(nn.Module):

    def __init__(self, block, layers, baseWidth = 26, scale = 2, num_classes=1000):
        self.inplanes = 64
        super(Res2Net, self).__init__()
        self.baseWidth = baseWidth
        self.scale = scale

        self.conv1 = nn.Conv1d(3, 64, kernel_size=7 , stride=2, padding=4,  #self.conv1 = nn.Conv1d(3, 64, kernel_size=7 , stride=2, padding=3,  
                               bias=False)
        
        self.bn1 = nn.BatchNorm1d(64)
        self.relu = nn.ReLU(inplace=True)
        # self.maxpool = nn.MaxPool1d(kernel_size=3, stride=2, padding=1)


        # self.shrinkage = Shrinkage(out_channels, gap_size=(1), reduction=reduction)


        # self.bn = nn.Sequential(
            
        #     nn.BatchNorm1d(256 * block.expansion),
        #     nn.ReLU(inplace=True),
        #     self.shrinkage #特征缩减
          
        # )

        self.layer1 = self._make_layer(block, 64, layers[0])
        self.BiLSTM1 = nn.LSTM(input_size=897,
                               hidden_size=448,
                               num_layers=1,
                               batch_first=True,
                               bidirectional=True,
                               dropout=0.5)
        self.layer2 = self._make_layer(block, 128, layers[1], stride=2)
        self.BiLSTM2 = nn.LSTM(input_size=448,
                               hidden_size=224,
                               num_layers=1,
                               batch_first=True,
                               bidirectional=True,
                               dropout=0.5)
        self.layer3 = self._make_layer(block, 64, layers[2], stride=2)
        self.BiLSTM3 = nn.LSTM(input_size=224,
                               hidden_size=112,
                               num_layers=1,
                               batch_first=True,
                               bidirectional=True,
                               dropout=0.5)
        self.layer4 = self._make_layer(block, 8, layers[3], stride=2)
        

        self.avgpool = nn.AdaptiveAvgPool1d(1)
        # self.fc = nn.Linear(256 * block.expansion, 112)
        # self.fc1 = nn.Linear(512 * block.expansion, 12)
        # self.fc2 = nn.Linear(512 * block.expansion, 4)
        

        for m in self.modules():
            if isinstance(m, nn.Conv1d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, nn.BatchNorm1d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

    def _make_layer(self, block, planes, blocks, stride=1):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(
                nn.Conv1d(self.inplanes, planes * block.expansion,
                          kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm1d(planes * block.expansion),
            )   # 检查是否进行下采样操作

        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample=downsample, 
                        stype='stage', baseWidth = self.baseWidth, scale=self.scale))
        self.inplanes = planes * block.expansion
        for i in range(1, blocks):
            layers.append(block(self.inplanes, planes, baseWidth = self.baseWidth, scale=self.scale))

        return nn.Sequential(*layers)
    
 


    def forward(self, x):

        # print(x.shape)
         
        x = self.conv1(x)

        x = self.bn1(x)
        x = self.relu(x)

        
    
        x = self.layer1(x)
        x, _ = self.BiLSTM1(x)
       
        x = self.layer2(x)
        x, _ = self.BiLSTM2(x)

        x = self.layer3(x)
        x, _ = self.BiLSTM3(x)

        x = self.layer4(x)


        


        # x = self.avgpool(x)
        # x = x.view(x.size(0), -1)
        # print(x.shape)
        # x = self.fc(x)
        # print(x.shape)
        
        # pos = self.fc1(x)
        # cls = self.fc2(x)

        return x





class CNN_LSTM(nn.Module):
    def __init__(self,  in_channel=3, kernel_size=3, in_embd=64, d_model=32, in_head=8, num_block=1, dropout=0, d_ff=128, out_num=12):
        # def __init__(self, in_channel=3, kernel_size=3, in_embd=128, d_model=512, in_head=8, num_block=1, dropout=0.3, d_ff=128, out_c=1):
        ##################  改动！！！

        '''
        :param in_embd: embedding
        :param d_model: embedding of transformer encoder
        :param in_head: mutil-heat attention
        :param dropout:
        :param d_ff: feedforward of transformer
        :param out_c: class_num
        '''
        super(CNN_LSTM, self).__init__()
        
        # self.sos = nn.Embedding(3, 1792)
        # self.flag = torch.LongTensor([0, 1, 2]).to(0)

        # self.backbone = nn.Sequential(
        #     DepthwiseSeparableConv1d(in_channels=in_channel, out_channels=32, kernel_size=kernel_size, stride=1, activate=True, bias=False),
        #     DepthwiseSeparableConv1d(in_channels=32, out_channels=64, kernel_size=kernel_size, stride=2, activate=True, bias=False),
        #     DepthwiseSeparableConv1d(in_channels=64, out_channels=in_embd, kernel_size=kernel_size, stride=2, activate=True, bias=False),
        # )
        
        

        self.backbone = Res2Net(Bottle2neck, [1, 1, 1, 1], baseWidth = 128, scale = 2)  # [3,4,23,3]
        # basewidth= 448   1792/448=4
        
        

        self.backbone1 = nn.Sequential(
            nn.Conv1d(3, 32, kernel_size=kernel_size, stride=4, padding=kernel_size // 2, bias=False),
            nn.BatchNorm1d(32),
            nn.ReLU(inplace=True),

            nn.Conv1d(32, 64, kernel_size=kernel_size, stride=4, padding=kernel_size // 2, bias=False),
            nn.BatchNorm1d(64),
            nn.ReLU(inplace=True),

            nn.Conv1d(64, 64, kernel_size=kernel_size, stride=1, padding=kernel_size // 2, bias=False),
            nn.BatchNorm1d(64),
            nn.ReLU(inplace=True),

            
            # DeformConv2d(32, 64, 3 , padding=1, modulation=True)

            nn.Conv1d(64, 64, kernel_size=kernel_size, stride=1, padding=kernel_size // 2, bias=False),
            nn.BatchNorm1d(64),
            nn.ReLU(inplace=True),
            nn.Conv1d(64, 64, kernel_size=kernel_size, stride=1, padding=kernel_size // 2, bias=False),
            nn.BatchNorm1d(64),
            nn.ReLU(inplace=True),
            nn.Conv1d(64, 32, kernel_size=kernel_size, stride=1, padding=kernel_size // 2, bias=False),
            nn.BatchNorm1d(32),
            nn.ReLU(inplace=True),
        )

        # self.enc_embedding_en = DataEmbedding(in_embd, d_model, dropout=dropout)
        # DataEmbedding数据嵌入模块，对输入的数据进行嵌入处理
        

        layers = []
        # for _ in range(num_block):
        #     layers.append(
        #         Encoder_exformer(
        #             layer=Attention(dim=d_model, num_heads=in_head, attn_drop=dropout, proj_drop=0.2),
        #             norm_layer=torch.nn.LayerNorm(d_model),
        #             d_model=d_model,
        #             dropout=dropout,
        #             d_ff=d_ff
        #         )
        #     )
        self.transformer_encoder = nn.Sequential(*layers)

        self.BiLSTM1 = nn.LSTM(input_size=112,
                               hidden_size=64,
                               num_layers=1,
                               batch_first=True,
                               bidirectional=True,
                               dropout=0.5)

        self.ap = nn.AdaptiveAvgPool1d(output_size=1)

        self.projetion_pos_1 = MLP(input_dim=128, hidden_dim=64, output_dim=32, num_layers=1)
        # self.projetion_pos_2 = MLP(input_dim=128, hidden_dim=64, output_dim=12, num_layers=1)
        self.projetion_cls = MLP(input_dim=113, hidden_dim=64, output_dim=4, num_layers=1)

        self.fc1 = nn.Linear(32 , 12)
        # self.fc2 = nn.Linear(128 , 4)
        


    def forward(self, x ):
        # print(x.shape)
        # x = self.backbone1(x)
        # print(x.shape)
    

        x = self.backbone1(x)  #[32, 128, 113]
        # print(x.shape)
        
        # x = x.permute(0, 2, 1)
        # print(x.shape)
        x, _ = self.BiLSTM1(x.permute(1, 0, 2))

###################################################################################
        
#         x = self.enc_embedding_en(x, None)

#         # print(x.shape)
       
#         x = self.transformer_encoder(x)
#         # print(x.shape)
  
#                
#         # print(x.shape)   
        x_1 = self.ap(x.permute(1, 2, 0)).squeeze(-1)  #注意：它和nn.Linear一样，如果你输入了一个三维的数据，他只会对最后一维的数据进行处理

#         # print(x_1.shape)
# ###############################################################################

        # if domain == 'source_train' or 'source_val':
        #     self.projetion_pos_1 = MLP(input_dim=128, hidden_dim=64, output_dim=6, num_layers=1).to(x_1.device)
        #     pos = self.projetion_pos_1(x_1)  #孔径位置信息
        # elif domain == 'target_val':
        #     self.projetion_pos_1 = MLP(input_dim=128, hidden_dim=64, output_dim=12, num_layers=1).to(x_1.device)
        #     pos = self.projetion_pos_1(x_1)  #孔径位置信息
        
        view = self.projetion_pos_1(x_1)  #孔径位置信息
        pos = self.fc1(view)
	
	
 

###############################################################################


        # print(pos.shape)
        # print(cls.shape)

 

        # x = self.ap(x.permute(0, 2, 1)).squeeze(-1)

        # out_x = self.projetion_huigui(x_1)
        # out_fenlei = self.projetion_leibie(x_1)



        # return out_huigui, out_fenlei, x.permute(1, 2, 0)[:, :, ::16]
        return pos,view




if __name__ == '__main__':

    parameter1 = 32
    x = torch.randn(parameter1, 2, 1792).to(0)

    model = Res2Net(Bottle2neck, [1, 1, 1, 1], baseWidth =32, scale = 2).to(0)  # [3,4,23,3]

    # model = model(in_channel=3, kernel_size=3, in_embd=64, d_model=112, in_head=2, num_block=1, d_ff=64, dropout=0.2, out_c=4).to(0)
    model_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print('Model total parameter: %.2fkb\n' % (model_params/1024))
    # print(model)

    # x = model(x)
    # print(x[0].shape)
    # print(x[1].shape)



    # summary(model,input_size=(64,64))
   

    # print(model)
    
    # summary(model, input_size=(2, 1792))
    # summary(model, input_size=(x))
