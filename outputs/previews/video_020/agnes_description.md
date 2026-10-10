

```json
{
  "sample_id": "video_020",
  "frame_analysis": [
    {
      "timestamp": "t=0.00s",
      "description": "整盆植物，正面视角，可见完整盆栽置于黄色桌面上，背景有床铺和衣物",
      "phase": "GLOBAL",
      "confidence": "HIGH"
    },
    {
      "timestamp": "t=3.67s",
      "description": "整盆植物，轻微角度变化，环绕运动开始",
      "phase": "GLOBAL",
      "confidence": "HIGH"
    },
    {
      "timestamp": "t=7.35s",
      "description": "整盆植物，继续环绕，角度进一步变化",
      "phase": "GLOBAL",
      "confidence": "HIGH"
    },
    {
      "timestamp": "t=11.02s",
      "description": "整盆植物，环绕持续，背景中可见黑色背包",
      "phase": "GLOBAL",
      "confidence": "HIGH"
    },
    {
      "timestamp": "t=14.70s",
      "description": "整盆植物，高角度俯视开始，顶部叶丛可见",
      "phase": "TRANSITION",
      "confidence": "MEDIUM"
    },
    {
      "timestamp": "t=18.37s",
      "description": "局部叶片特写，近距离，顶部视角，叶脉纹理清晰",
      "phase": "LOCAL",
      "confidence": "HIGH"
    },
    {
      "timestamp": "t=22.05s",
      "description": "局部叶片极度近距离，顶部俯视，几乎充满画面",
      "phase": "LOCAL",
      "confidence": "HIGH"
    },
    {
      "timestamp": "t=25.72s",
      "description": "整盆植物，高角度俯视，可见黄色桌面全貌",
      "phase": "GLOBAL",
      "confidence": "HIGH"
    },
    {
      "timestamp": "t=29.40s",
      "description": "局部叶片极度近距离特写，几乎无法辨识整体形态",
      "phase": "LOCAL",
      "confidence": "HIGH"
    },
    {
      "timestamp": "t=33.07s",
      "description": "整盆植物，高角度俯视，回到全局视角",
      "phase": "GLOBAL",
      "confidence": "HIGH"
    }
  ],
  "global_and_local_simultaneous": false,
  "suitability_for_mixed_distance_sfm": {
    "suitable": true,
    "reasons": [
      "视频包含明确的 GLOBAL→LOCAL→GLOBAL 距离变化序列，适合诊断多尺度 SfM 性能",
      "存在多个高度重叠的全局帧（t=0.00s, 3.67s, 7.35s, 11.02s, 25.72s, 33.07s），可评估环绕运动的轨迹一致性",
      "局部帧（t=18.37s, 22.05s, 29.40s）提供近距纹理特征，可测试小基线匹配与深度估计",
      "过渡帧（t=14.70s）显示从全局到局部的平滑移动，适合分析重投影误差的连续性",
      "植物具有重复叶脉纹理，可评估纹理重复区域对 SfM 的影响",
      "静态背景（黄色桌面、室内环境）提供稳定参照，便于分离相机运动与场景结构"
    ]
  }
}
```