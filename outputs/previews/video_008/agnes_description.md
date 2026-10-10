

```json
{
  "sample_id": "video_008",
  "frame_analysis": [
    {
      "timestamp": "t=0.00s",
      "stage": "GLOBAL",
      "confidence": 0.92,
      "description": "整盆植物中景，可见花盆、桌面及背景环境（自行车轮、家居）"
    },
    {
      "timestamp": "t=5.07s",
      "stage": "GLOBAL",
      "confidence": 0.85,
      "description": "整盆植物，有喷壶入画，视角略近，背景仍清晰可见"
    },
    {
      "timestamp": "t=10.14s",
      "stage": "GLOBAL",
      "confidence": 0.90,
      "description": "整盆植物中景，坐姿视角，背景为家居环境"
    },
    {
      "timestamp": "t=15.21s",
      "stage": "GLOBAL",
      "confidence": 0.90,
      "description": "整盆植物，略高角度，桌面与背景完整可见"
    },
    {
      "timestamp": "t=20.28s",
      "stage": "GLOBAL",
      "confidence": 0.88,
      "description": "较高俯视角度的整盆植物，桌面与背景清晰"
    },
    {
      "timestamp": "t=25.34s",
      "stage": "APPROACH",
      "confidence": 0.72,
      "description": "植物占据更大画面，背景开始模糊，接近全局与局部过渡区域"
    },
    {
      "timestamp": "t=30.41s",
      "stage": "LOCAL",
      "confidence": 0.82,
      "description": "近距离拍摄，主要呈现叶片细节，背景显著弱化"
    },
    {
      "timestamp": "t=35.48s",
      "stage": "LOCAL",
      "confidence": 0.90,
      "description": "近距离俯拍，几乎完全由叶片和顶部构成"
    },
    {
      "timestamp": "t=40.55s",
      "stage": "LOCAL",
      "confidence": 0.93,
      "description": "极近距离俯视，叶片填满画面，背景仅少量可见"
    },
    {
      "timestamp": "t=45.62s",
      "stage": "GLOBAL",
      "confidence": 0.88,
      "description": "中远景，整盆植物完整可见，桌面与背景恢复"
    }
  ],
  "global_and_local_present": true,
  "sfm_diagnostic_suitability": {
    "suitable": false,
    "reasons": [
      "距离变化虽有但缺乏连续性过渡——从GLOBAL直接跳至LOCAL，缺少稳定的APPROACH/RETREAT序列，不利于重建连续相机轨迹",
      "多帧场景视角相似（t=0~20s均为相似GLOBAL角度），特征点覆盖重复度高，视差增量不足",
      "LOCAL帧（t=30~40s）与GLOBAL帧（t=45s）之间存在明显的景别断层，可能导致特征匹配跨距离失败",
      "背景干扰元素较多（自行车、家具、地板花纹），可能引入非植物区域的稳定特征，干扰 SfM 对主体结构的重建",
      "样本帧数仅10帧，时间跨度45s，采样密度过低，无法保证关键帧覆盖完整的运动变化"
    ]
  }
}
```