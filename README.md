# README.md

# 弱网场景下视频流传输系统

这是一个针对弱网场景的视频流传输优化系统，能够动态地根据网络状态(如带宽波动、高延迟、高丢包率)对网络传输及视频编码方法进行优化(如自适应码率、智能纠错等)，以保障视频传输质量和用户体验。

## 功能特点

1. **智能感知编码(ROI-based Encoding)**：基于鼠标位置和内容重要性进行区域优先编码
2. **预测性网络适应(Predictive Network Adaptation)**：预测网络变化并提前调整编码参数
3. **混合恢复技术(Hybrid Recovery)**：结合FEC、选择性重传和AI辅助帧重建

## 系统要求

- Python 3.8或更高版本
- Windows 10操作系统

## 安装

1. 克隆仓库：
git clone https://github.com/yourusername/weak-network-video-streaming.git
cd weak-network-video-streaming

2. 安装依赖：
pip install -r requirements.txt

## 使用方法

### 启动服务端
python server/main.py [--port PORT] [--width WIDTH] [--height HEIGHT] [--fps FPS] [--nogui]

参数说明：
- `--port`: 服务器端口，默认为8000
- `--width`: 视频宽度，默认为1280
- `--height`: 视频高度，默认为720
- `--fps`: 目标帧率，默认为30
- `--nogui`: 无GUI模式运行

### 启动客户端
python client/main.py SERVER_HOST [--port PORT] [--nogui]

参数说明：
- `SERVER_HOST`: 服务器主机名或IP地址
- `--port`: 服务器端口，默认为8000
- `--nogui`: 无GUI模式运行

## 测试网络条件

可以使用clumsy工具模拟各种网络条件进行测试：

1. 良好网络: 延迟=50ms, 丢包=1%
2. 中等网络: 延迟=100ms, 丢包=1%
3. 弱网: 延迟=200ms, 丢包=1%
4. 严重弱网: 延迟=300ms, 丢包=2%
5. 极端弱网: 延迟=400ms, 丢包=2%

## 架构设计

系统采用客户端-服务器架构，主要模块包括：

### 服务端
- 屏幕捕获模块
- 视频编码模块(带ROI优化)
- 网络传输模块(带FEC和预测性调整)

### 客户端
- 网络接收模块
- 视频解码模块
- 帧重建模块
- 渲染显示模块

## 许可证

MIT



weak-network-video-streaming/
├── __init__.py                           # 项目根目录标记为Python包
│
├── server/                               # 服务端代码
│   ├── __init__.py                       # 标记为Python包
│   ├── main.py                           # 服务端入口
│   │
│   ├── capture/                          # 屏幕捕获模块
│   │   ├── __init__.py                   # 标记为Python包
│   │   └── screen_capturer.py            # 屏幕捕获器
│   │
│   ├── encoder/                          # 视频编码模块
│   │   ├── __init__.py                   # 标记为Python包
│   │   ├── video_encoder.py              # 基本视频编码器
│   │   ├── adaptive_encoder.py           # 自适应视频编码器
│   │   └── roi_detector.py               # ROI检测器
│   │
│   └── network/                          # 网络传输模块
│       ├── __init__.py                   # 标记为Python包
│       └── transport_server.py           # 传输服务器
│
├── client/                               # 客户端代码
│   ├── __init__.py                       # 标记为Python包
│   ├── main.py                           # 客户端入口
│   │
│   ├── decoder/                          # 视频解码模块
│   │   ├── __init__.py                   # 标记为Python包
│   │   ├── video_decoder.py              # 视频解码器
│   │   └── frame_reconstruction.py       # 帧重建器
│   │
│   ├── renderer/                         # 视频渲染模块
│   │   ├── __init__.py                   # 标记为Python包
│   │   └── frame_renderer.py             # 帧渲染器
│   │
│   └── network/                          # 网络接收模块
│       ├── __init__.py                   # 标记为Python包
│       └── transport_client.py           # 传输客户端
│
├── common/                               # 公共代码
│   ├── __init__.py                       # 标记为Python包
│   ├── config.py                         # 配置文件
│   ├── utils.py                          # 通用工具函数
│   │
│   └── network_utils/                    # 网络工具
│       ├── __init__.py                   # 标记为Python包
│       ├── protocol.py                   # 自定义协议实现
│       └── monitoring.py                 # 网络监控
│
├── models/                               # AI模型
│   ├── __init__.py                       # 标记为Python包
│   │
│   ├── network_prediction/               # 网络预测模型
│   │   ├── __init__.py                   # 标记为Python包
│   │   └── lstm_predictor.py             # LSTM预测模型 (未实现)
│   │
│   └── frame_reconstruction/             # 帧重建模型
│       ├── __init__.py                   # 标记为Python包
│       └── frame_interpolator.py         # 帧插值模型 (未实现)
│
├── ui/                                   # 用户界面
│   ├── __init__.py                       # 标记为Python包
│   │
│   ├── server_ui/                        # 服务端界面
│   │   ├── __init__.py                   # 标记为Python包
│   │   └── server_gui.py                 # 服务端GUI
│   │
│   └── client_ui/                        # 客户端界面
│       ├── __init__.py                   # 标记为Python包
│       └── client_gui.py                 # 客户端GUI
│
├── tests/                                # 测试代码 (未实现)
│   ├── __init__.py                       # 标记为Python包
│   │
│   ├── performance_tests/                # 性能测试
│   │   ├── __init__.py                   # 标记为Python包
│   │   └── benchmark.py                  # 基准测试 (未实现)
│   │
│   └── network_simulation/               # 网络模拟测试
│       ├── __init__.py                   # 标记为Python包
│       └── simulate.py                   # 网络模拟 (未实现)
│
├── docs/                                 # 文档 (未实现)
│   ├── design/                           # 设计文档
│   │   └── architecture.md               # 架构设计 (未实现)
│   │
│   └── user_manual/                      # 用户手册
│       └── manual.md                     # 使用说明 (未实现)
│
├── requirements.txt                      # 依赖项
└── README.md                             # 项目说明




系统涵盖了题目要求的所有功能，并包含了三个创新点：

智能感知编码(ROI-based Encoding)
预测性网络适应(Predictive Network Adaptation)
混合恢复技术(Hybrid Recovery)