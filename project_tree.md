### weak-network-video-streaming目录结构如下所示：
```tree
.
weak-network-video-streaming/
│
├── server/                      # 服务端代码
│   ├── __init__.py
│   ├── main.py                  # 服务端主入口
│   ├── screen_capture.py        # 屏幕捕获模块
│   ├── video_encoder.py         # 视频编码模块
│   ├── roi_detector.py          # ROI检测和处理模块
│   ├── network/                 # 网络相关模块
│   │   ├── __init__.py
│   │   ├── quic_server.py       # QUIC服务器实现
│   │   └── network_monitor.py   # 网络状态监测
│   └── utils/                   # 工具函数
│       ├── __init__.py
│       ├── config.py            # 配置管理
│       └── logger.py            # 日志工具
│
├── client/                      # 客户端代码
│   ├── __init__.py
│   ├── main.py                  # 客户端主入口
│   ├── video_decoder.py         # 视频解码模块
│   ├── video_renderer.py        # 视频渲染模块
│   ├── network/                 # 网络相关模块
│   │   ├── __init__.py
│   │   ├── quic_client.py       # QUIC客户端实现
│   │   └── network_analyzer.py  # 网络质量分析
│   ├── ui/                      # 用户界面
│   │   ├── __init__.py
│   │   ├── main_window.py       # 主窗口
│   │   ├── video_widget.py      # 视频显示组件
│   │   └── network_status.py    # 网络状态显示组件
│   └── utils/                   # 工具函数
│       ├── __init__.py
│       ├── config.py            # 配置管理
│       └── logger.py            # 日志工具
│
├── common/                      # 服务端和客户端共享代码
│   ├── __init__.py
│   ├── constants.py             # 共享常量
│   ├── protocol.py              # 通信协议定义
│   ├── packet.py                # 数据包定义
│   └── utils/                   # 共享工具函数
│       ├── __init__.py
│       └── metrics.py           # 性能度量工具
│
├── tests/                       # 测试代码
│   ├── __init__.py
│   ├── test_roi_detector.py     # ROI检测测试
│   ├── test_video_codec.py      # 视频编解码测试
│   ├── test_quic.py             # QUIC协议测试
│   └── test_integration.py      # 集成测试
│
├── scripts/                     # 实用脚本
│   ├── setup_environment.py     # 环境配置脚本
│   ├── run_server.py            # 服务端启动脚本
│   └── run_client.py            # 客户端启动脚本
│
├── config/                      # 配置文件
│   ├── server_config.yaml       # 服务端配置
│   ├── client_config.yaml       # 客户端配置
│   └── logging_config.yaml      # 日志配置
│
├── docs/                        # 文档
│   ├── architecture.md          # 架构文档
│   ├── protocol.md              # 协议文档
│   └── usage.md                 # 使用说明
│
├── requirements.txt             # 依赖包列表
├── setup.py                     # 安装脚本
└── README.md                    # 项目说明
```
